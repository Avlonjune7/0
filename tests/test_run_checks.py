import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1] / "skills" / "0-build" / "scripts" / "run_checks.py"
)


class RunChecksTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.root = self.workspace / "项目 根"
        self.root.mkdir()
        self.manifest = self.workspace / "checks.json"

    def invoke(self, commands, *flags):
        self.manifest.write_text(json.dumps(commands, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT),
             "--root", str(self.root), "--commands", str(self.manifest), *flags],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(process.stderr, "", process.stderr)
        return process.returncode, json.loads(process.stdout)

    def check(self, name, script, *args, **fields):
        return {"name": name, "argv": [sys.executable, "-B", "-X", "utf8", "-c", script, *args], **fields}

    def test_reports_pass_and_preserves_unicode_arguments_and_cwd(self):
        subdir = self.root / "验证 文件"
        subdir.mkdir()
        argument = "中文 空格 & | ^ %VAR%"
        status, report = self.invoke([
            self.check("中文检查", "import pathlib,sys; print(pathlib.Path.cwd().name); print(sys.argv[1])",
                       argument, cwd=subdir.name),
        ])
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "passed")
        result, = report["results"]
        self.assertEqual(result["name"], "中文检查")
        self.assertEqual(Path(result["cwd"]), subdir.resolve())
        self.assertEqual(result["output_tail"].splitlines(), [subdir.name, argument])
        self.assertEqual(result["exit_code"], 0)
        self.assertIsNone(result["launch_error"])
        self.assertGreaterEqual(result["duration_ms"], 0)

    def test_reports_failure_bounded_output_and_missing_executable(self):
        status, report = self.invoke([
            self.check("fails", "import sys; print('dropped-prefix' + 'x' * 20000, flush=True); "
                       "print('失败详情', file=sys.stderr); sys.exit(7)"),
            {"name": "missing", "argv": [str(self.root / "no-such-executable.exe")]},
        ])
        self.assertEqual(status, 1)
        self.assertEqual(report["status"], "failed")
        failure, missing = report["results"]
        self.assertEqual(failure["exit_code"], 7)
        self.assertTrue(failure["output_truncated"])
        self.assertNotIn("dropped-prefix", failure["output_tail"])
        self.assertLessEqual(len(failure["output_tail"].encode("utf-8")), 8192)
        self.assertTrue(failure["output_tail"].rstrip().endswith("失败详情"))
        self.assertIsNone(missing["exit_code"])
        self.assertTrue(missing["launch_error"])

    def test_validates_all_checks_before_any_process_starts(self):
        first = self.check("marker", "from pathlib import Path; Path('started').touch()")
        invalid_items = [
            {"name": "invalid argv", "argv": ["tool", 5]},
            {"name": "invalid key", "argv": ["tool"], "cdw": "other"},
            {"name": "outside checkout", "argv": ["tool"], "cwd": ".."},
            {"name": "bad timeout", "argv": ["tool"], "timeout_sec": 0},
            {"name": "bool timeout", "argv": ["tool"], "timeout_sec": True},
            {"name": "marker", "argv": ["tool"]},
        ]
        if os.name == "nt":
            invalid_items.extend([
                {"name": "batch", "argv": ["tool.cmd"]},
                {"name": "batch with trailing space", "argv": ["tool.BAT "]},
            ])
        for invalid in invalid_items:
            with self.subTest(invalid=invalid):
                status, report = self.invoke([first, invalid], "--jobs", "2")
                self.assertEqual(status, 2)
                self.assertEqual(report["status"], "invalid_input")
                self.assertFalse((self.root / "started").exists())

    @unittest.skipUnless(os.name == "nt", "Windows batch invocation")
    def test_runs_batch_via_explicit_cmd(self):
        (self.root / "check.cmd").write_text("@echo native-batch\n", encoding="ascii")
        status, report = self.invoke([
            {"name": "batch", "argv": ["cmd.exe", "/d", "/c", "check.cmd"]},
        ])
        self.assertEqual(status, 0, report)
        self.assertEqual(report["results"][0]["output_tail"].strip(), "native-batch")

    def test_runs_independent_checks_concurrently_and_keeps_manifest_order(self):
        handshake = """
from pathlib import Path
import sys
import time

my_marker, peer_marker = map(Path, sys.argv[1:])
my_marker.touch()
deadline = time.monotonic() + 6
while not peer_marker.exists():
    if time.monotonic() > deadline:
        raise SystemExit('peer did not run concurrently')
    time.sleep(0.01)
"""
        status, report = self.invoke([
            self.check("first", handshake, "first.ready", "second.ready"),
            self.check("second", handshake, "second.ready", "first.ready"),
        ], "--jobs", "2")
        self.assertEqual(status, 0, report)
        self.assertEqual([result["name"] for result in report["results"]], ["first", "second"])
        self.assertTrue((self.root / "first.ready").is_file())
        self.assertTrue((self.root / "second.ready").is_file())

    def test_reports_timeout_and_terminates_hanging_check(self):
        status, report = self.invoke([
            self.check("hang", "import time; print('before-timeout', flush=True); time.sleep(10)", timeout_sec=0.3),
            self.check("fast", "print('ok')"),
        ])
        self.assertEqual(status, 1)
        self.assertEqual(report["status"], "failed")
        hang, fast = report["results"]
        self.assertTrue(hang["timed_out"])
        self.assertIsNone(hang["exit_code"])
        self.assertIn("before-timeout", hang["output_tail"])
        self.assertFalse(fast["timed_out"])
        self.assertEqual(fast["exit_code"], 0)

    def test_rejects_negative_cli_timeout(self):
        status, report = self.invoke([self.check("ok", "print('ok')")], "--timeout", "-1")
        self.assertEqual(status, 2)
        self.assertEqual(report["status"], "invalid_input")

    def test_timeout_terminates_descendant_process_tree(self):
        marker = self.root / "descendant-wrote.txt"
        launcher = (
            "import pathlib, subprocess, sys, time; "
            "child = subprocess.Popen([sys.executable, '-B', '-c', "
            "\"import pathlib, sys, time; time.sleep(1.5); pathlib.Path(sys.argv[1]).write_text('late')\", "
            "sys.argv[1]]); "
            "child.wait()"
        )
        status, report = self.invoke([
            self.check("tree", launcher, str(marker), timeout_sec=0.4),
        ])
        self.assertEqual(status, 1)
        result, = report["results"]
        self.assertTrue(result["timed_out"])
        self.assertLess(result["duration_ms"], 3500)
        import time
        time.sleep(1.8)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
