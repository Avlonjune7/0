import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "skills" / "0-setup" / "scripts" / "scan_project.py"


class ScanProjectTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.workspace = Path(workspace.name)
        self.root = self.workspace / "项目 示例"
        self.root.mkdir()

    def scan(self, root=None, *args):
        return subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--root", str(root or self.root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def write(self, relative, content="sample\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def report(self, root=None, *args):
        run = self.scan(root, *args)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_empty_directory(self):
        report = self.report()
        self.assertEqual(report["scan_method"], "filesystem")
        self.assertEqual(report["files_scanned"], 0)
        self.assertFalse(report["truncated"])
        self.assertEqual(report["documents"], [])
        self.assertEqual(report["configurations"], [])
        self.assertEqual(report["candidate_source_dirs"], [])

    def test_filesystem_inventory_skips_generated_and_private_env_files(self):
        self.write("README.md")
        self.write("docs/功能说明.md")
        self.write("package.json")
        self.write(".env.example")
        self.write(".env.override", "private-value")
        self.write("src/查询/入口.ts")
        self.write("node_modules/pkg/README.md")
        self.write("build/generated.py")
        report = self.report()
        self.assertEqual(report["files_scanned"], 5)
        self.assertEqual(report["documents"], ["README.md", "docs/功能说明.md"])
        self.assertEqual(report["configurations"], [".env.example", "package.json"])
        self.assertEqual(report["candidate_source_dirs"], ["src/查询"])
        self.assertNotIn("private-value", json.dumps(report))

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_git_ignored_untracked_files_and_subdirectory_boundary(self):
        self.git("init", "-q")
        self.write(".gitignore", "ignored.md\ntracked.md\n")
        self.write("README.md")
        self.write("模块/ignored.md")
        self.write("模块/tracked.md")
        self.git("add", "-f", "模块/tracked.md")
        self.write("模块/新文档.md")
        self.write("模块/代码.py")
        self.write("模块/dist/build.py")
        self.write("模块/removed.md")
        self.git("add", "模块/removed.md")
        (self.root / "模块/removed.md").unlink()
        report = self.report(self.root / "模块")
        self.assertEqual(report["scan_method"], "git")
        self.assertEqual(report["documents"], ["tracked.md", "新文档.md"])
        self.assertEqual(report["candidate_source_dirs"], ["."])
        self.assertEqual(report["files_scanned"], 3)

    def test_truncation_counts_eligible_files(self):
        self.write("A.md")
        self.write("B.md")
        self.write("node_modules/ignored.md")
        limited = self.report(None, "--max-files", "1")
        exact = self.report(None, "--max-files", "2")
        self.assertEqual(limited["files_scanned"], 1)
        self.assertEqual(limited["documents"], ["A.md"])
        self.assertTrue(limited["truncated"])
        self.assertEqual(exact["files_scanned"], 2)
        self.assertFalse(exact["truncated"])

    def test_directory_link_does_not_extend_scope(self):
        outside = self.workspace / "other"
        outside.mkdir()
        (outside / "external.md").touch()
        try:
            (self.root / "redirect").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlink unavailable: {error}")
        self.assertEqual(self.report()["files_scanned"], 0)
        self.assertEqual(self.scan(self.root / "redirect").returncode, 2)

    @unittest.skipUnless(sys.platform == "win32", "junctions are Windows-specific")
    def test_directory_junction_does_not_extend_scope(self):
        import _winapi

        outside = self.workspace / "other"
        outside.mkdir()
        (outside / "external.md").touch()
        try:
            _winapi.CreateJunction(str(outside), str(self.root / "redirect"))
        except OSError as error:
            self.skipTest(f"junction unavailable: {error}")
        self.assertEqual(self.report()["files_scanned"], 0)
        self.assertEqual(self.scan(self.root / "redirect").returncode, 2)

    def test_missing_root_and_nonpositive_limit_are_errors(self):
        self.assertEqual(self.scan(self.root / "missing").returncode, 2)
        self.assertEqual(self.scan(None, "--max-files", "0").returncode, 2)

    def test_ignores_inherited_git_dir_and_work_tree_env(self):
        import os

        other = self.workspace / "other-repo"
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-b", "main"], check=True, capture_output=True)
        (other / "foreign.md").write_text("foreign", encoding="utf-8")
        (self.root / "local.md").write_text("local", encoding="utf-8")
        env = {
            **os.environ,
            "GIT_DIR": str(other / ".git"),
            "GIT_WORK_TREE": str(other),
        }
        process = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", env=env, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["documents"], ["local.md"])


if __name__ == "__main__":
    unittest.main()
