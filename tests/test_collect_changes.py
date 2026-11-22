import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "skills/0-review/scripts/collect_changes.py"


class CollectChangesTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="git-changes-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Fixture",
             "-c", "user.email=fixture@example.test", "-c", "commit.gpgsign=false",
             *arguments],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8").strip()

    def collect(self, *arguments, status=0, root=None, env=None):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(SCRIPT),
             "--root", str(self.root if root is None else root), *arguments],
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def init(self):
        self.git("init", "--quiet", "--template=")

    def write(self, path, contents):
        (self.root / path).write_text(contents, encoding="utf-8")

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", message)
        return self.git("rev-parse", "HEAD")

    def test_no_repository(self):
        result = self.collect()
        self.assertEqual(result["repository"], "none")
        self.assertEqual(result["mode"], "worktree")
        self.assertEqual(Path(result["root"]), self.root)
        self.assertNotIn("staged", result)
        self.assertIn("error", self.collect("--head", "HEAD", status=1))

    def test_unborn_repository_with_staged_and_untracked_files(self):
        self.init()
        empty = self.collect()
        self.assertEqual(empty["repository"], "git")
        self.assertTrue(empty["unborn"])
        self.assertIsNone(empty["head"])
        self.assertEqual(empty["staged"], [])
        self.assertEqual(empty["unstaged"], [])
        self.assertEqual(empty["untracked"], [])

        self.write("暂存 空格.txt", "staged")
        self.git("add", "--", "暂存 空格.txt")
        self.write("未跟踪 空格.txt", "untracked")
        result = self.collect()
        self.assertTrue(result["unborn"])
        self.assertEqual(result["staged"], [{"status": "A", "path": "暂存 空格.txt"}])
        self.assertEqual(result["unstaged"], [])
        self.assertEqual(result["untracked"], ["未跟踪 空格.txt"])

    def test_worktree_keeps_index_and_worktree_changes_separate(self):
        self.init()
        self.write("旧 名.txt", "unchanged after rename")
        self.write("tracked.txt", "base")
        self.write(".gitignore", "ignored.txt\n")
        head = self.commit("baseline")
        self.git("mv", "--", "旧 名.txt", "新 名.txt")
        self.write("tracked.txt", "staged only")
        self.git("add", "--", "tracked.txt")
        self.write("tracked.txt", "base")
        self.write("待 审.txt", "untracked")
        self.write("ignored.txt", "ignored")
        subdirectory = self.root / "nested"
        subdirectory.mkdir()

        index = self.root / ".git/index"
        before = index.read_bytes(), index.stat().st_mtime_ns
        result = self.collect(root=subdirectory)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertEqual(Path(result["root"]), self.root)
        self.assertEqual(result["head"], head)
        self.assertFalse(result["unborn"])
        self.assertCountEqual(result["staged"], [
            {"status": "R100", "old_path": "旧 名.txt", "path": "新 名.txt"},
            {"status": "M", "path": "tracked.txt"},
        ])
        self.assertEqual(result["unstaged"], [{"status": "M", "path": "tracked.txt"}])
        self.assertEqual(result["untracked"], ["待 审.txt"])

    def test_commit_range_resolves_endpoints_and_excludes_worktree_changes(self):
        self.init()
        self.write("original.txt", "same after rename")
        base = self.commit("baseline")
        self.git("mv", "--", "original.txt", "renamed 中文.txt")
        self.write("committed.txt", "committed")
        head = self.commit("committed rename and addition")
        self.write("staged.txt", "staged")
        self.git("add", "--", "staged.txt")
        self.write("committed.txt", "unstaged")
        self.write("untracked.txt", "untracked")

        result = self.collect("--base", base[:10], "--head", "HEAD")
        self.assertEqual(result["mode"], "commits")
        self.assertEqual(result["base"], base)
        self.assertEqual(result["head"], head)
        self.assertCountEqual(result["changes"], [
            {"status": "A", "path": "committed.txt"},
            {"status": "R100", "old_path": "original.txt", "path": "renamed 中文.txt"},
        ])
        self.assertNotIn("staged", result)
        self.assertEqual(self.collect("--base", base), result)
        self.assertEqual(self.collect("--head", head), result)

        root_commit = self.collect("--head", base)
        self.assertIsNone(root_commit["base"])
        self.assertEqual(root_commit["head"], base)
        self.assertEqual(root_commit["changes"], [{"status": "A", "path": "original.txt"}])

    def test_invalid_commit_ref_is_a_collection_error(self):
        self.init()
        self.write("tracked.txt", "baseline")
        self.commit("baseline")
        result = self.collect("--base", "no-such-revision", status=1)
        self.assertIn("no-such-revision", result["error"])

    def test_merge_requires_an_explicit_base(self):
        self.init()
        self.write("tracked.txt", "baseline")
        base = self.commit("baseline")
        self.write("tracked.txt", "modified")
        parent = self.commit("modification")
        tree = self.git("rev-parse", "HEAD^{tree}")
        merge = self.git("commit-tree", tree, "-p", parent, "-p", base, "-m", "merge")

        ambiguous = self.collect("--head", merge, status=1)
        self.assertIn("--base", ambiguous["error"])
        result = self.collect("--base", base, "--head", merge)
        self.assertEqual(result["changes"], [{"status": "M", "path": "tracked.txt"}])

    def test_missing_git_executable_is_a_collection_error(self):
        result = self.collect(status=1, env={**os.environ, "PATH": ""})
        self.assertIn("git", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
