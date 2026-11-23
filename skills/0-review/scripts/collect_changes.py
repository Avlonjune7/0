"""List Git change paths as JSON, keeping commit and worktree scopes separate."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


GIT_REPO_ENV_VARS = {
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
}


def clean_git_env():
    env = {k: v for k, v in os.environ.items() if k not in GIT_REPO_ENV_VARS}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    return env


def run_git(root, *arguments, check=True):
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *arguments],
            env=clean_git_env(),
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        raise ValueError("Git executable was not found.") from None
    if check and result.returncode:
        error = result.stderr.decode("utf-8", "replace").strip()
        raise ValueError(error or f"Git exited with status {result.returncode}")
    return result


def split_paths(output):
    if not output:
        return []
    return output.removesuffix(b"\0").decode("utf-8", "surrogateescape").split("\0")


def diff_entries(output):
    parts = iter(split_paths(output))
    entries = []
    for status in parts:
        path = next(parts)
        if status.startswith(("R", "C")):
            entries.append({"status": status, "old_path": path, "path": next(parts)})
        else:
            entries.append({"status": status, "path": path})
    return entries


def resolve_commit(root, ref):
    result = run_git(root, "rev-parse", "--verify", "--quiet", "--end-of-options",
                     f"{ref}^{{commit}}", check=False)
    if result.returncode:
        raise ValueError(f"Cannot resolve a commit for {ref!r}.")
    return result.stdout.decode("ascii").strip()


DIFF_OPTIONS = ("--name-status", "-z", "--find-renames",
                "--no-ext-diff", "--no-textconv", "--ignore-submodules=none")


def worktree_changes(root):
    result = run_git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}",
                     check=False)
    if result.returncode:
        run_git(root, "symbolic-ref", "--quiet", "HEAD")
        head = None
        # Git compares the index to the empty tree before the initial commit.
        baseline = ()
    else:
        head = result.stdout.decode("ascii").strip()
        baseline = (head,)
    staged = run_git(root, "diff", "--cached", *DIFF_OPTIONS, *baseline, "--").stdout
    unstaged = run_git(root, "diff", *DIFF_OPTIONS, "--").stdout
    untracked = run_git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    return {
        "head": head,
        "unborn": head is None,
        "staged": diff_entries(staged),
        "unstaged": diff_entries(unstaged),
        "untracked": split_paths(untracked),
    }


def commit_changes(root, base_ref, head_ref):
    head = resolve_commit(root, head_ref if head_ref is not None else "HEAD")
    if base_ref is not None:
        base = resolve_commit(root, base_ref)
    else:
        _, *parents = run_git(root, "rev-list", "--parents", "-n", "1", head, "--").stdout.split()
        if len(parents) > 1:
            raise ValueError("Merge commit requires an explicit --base.")
        base = parents[0].decode("ascii") if parents else None

    if base is not None:
        output = run_git(root, "diff", *DIFF_OPTIONS, base, head, "--").stdout
    else:
        if run_git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
            raise ValueError("Cannot establish commit parent in a shallow repository. Supply --base.")
        output = run_git(root, "diff-tree", "--root", "--no-commit-id", "-r",
                         *DIFF_OPTIONS, head, "--").stdout
    return {"base": base, "head": head, "changes": diff_entries(output)}


def collect(root, base, head):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Root is not a directory: {root}")

    mode = "commits" if base is not None or head is not None else "worktree"
    result = run_git(root, "rev-parse", "--show-toplevel", check=False)
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace").strip()
        if error.startswith("fatal: not a git repository") and mode == "worktree":
            return {"repository": "none", "mode": mode, "root": str(root)}
        raise ValueError(error or f"Git exited with status {result.returncode}")

    root = Path(os.fsdecode(result.stdout.removesuffix(b"\n")))
    changes = worktree_changes(root) if mode == "worktree" else commit_changes(root, base, head)
    return {"repository": "git", "mode": mode, "root": str(root), **changes}


def main():
    parser = argparse.ArgumentParser(
        description="List changed paths from a Git worktree or fixed commits as JSON. "
                    "No refs: return staged, unstaged, and untracked paths separately. "
                    "Outside Git, return repository=none in worktree mode.",
        epilog="Commit ranges use direct endpoint comparison. For a PR, pass its "
               "merge base as --base. With --head alone, compare its parent to the "
               "commit. For a merge commit, specify --base. JSON paths are relative "
               "to the detected repository root. Exit 1 reports a collection error.",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="directory inside the project (default: current directory)")
    parser.add_argument("--base", help="starting commit. If --head is omitted, compare to HEAD")
    parser.add_argument("--head", help="ending commit. A commit range excludes worktree changes")
    args = parser.parse_args()
    try:
        result = collect(args.root, args.base, args.head)
    except (OSError, ValueError) as exc:
        result, exit_code = {"error": str(exc)}, 1
    else:
        exit_code = 0
    # UTF-8 for readable paths; escape any non-UTF-8 Git path bytes as surrogates.
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
