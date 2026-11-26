#!/usr/bin/env python3
"""Collect a deterministic project baseline snapshot for 0-optimize."""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

SKIP_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "vendor", "__pycache__",
    ".next", ".nuxt", ".pytest_cache", "build", "dist", "coverage", "target", ".turbo",
}
SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".dart", ".ex", ".exs", ".fs", ".go", ".h", ".hpp",
    ".java", ".js", ".jsx", ".kt", ".lua", ".mjs", ".cjs", ".php", ".py", ".rb",
    ".rs", ".scala", ".sh", ".ps1", ".sql", ".svelte", ".swift", ".ts", ".tsx", ".vue",
}
GIT_REPO_ENV_VARS = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
    "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
}
TOOL_PROBES = {
    "frontend": ("lighthouse", "npx", "playwright"),
    "backend": ("k6", "oha", "go", "pytest", "py-spy"),
    "static": ("scc", "jscpd", "knip", "golangci-lint", "ruff", "eslint"),
}


def entry_stat(path: Path):
    try:
        info = path.lstat()
    except (FileNotFoundError, NotADirectoryError, OSError):
        return None
    if stat.S_ISLNK(info.st_mode):
        return None
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return None
    return info


def iter_project_files(root: Path):
    exclusions = [f"--exclude={d}/" for d in sorted(SKIP_DIRECTORIES)]
    git_env = {k: v for k, v in os.environ.items() if k not in GIT_REPO_ENV_VARS}
    git_env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", *exclusions, "--"],
            env=git_env, capture_output=True, check=False,
        )
        use_git = listing.returncode == 0
    except OSError:
        listing = None
        use_git = False

    if use_git and listing is not None:
        seen = set()
        for raw in listing.stdout.split(b"\0"):
            if not raw or raw in seen:
                continue
            seen.add(raw)
            rel = Path(os.fsdecode(raw))
            if rel.anchor or ".." in rel.parts:
                continue
            if any(p.casefold() in SKIP_DIRECTORIES for p in rel.parts[:-1]):
                continue
            info = entry_stat(root / rel)
            if info is not None and stat.S_ISREG(info.st_mode):
                yield rel, info.st_size
        return

    for loc, dirs, files in os.walk(root):
        cur = Path(loc)
        dirs[:] = sorted(
            d for d in dirs
            if d.casefold() not in SKIP_DIRECTORIES and entry_stat(cur / d) is not None
        )
        for name in sorted(files):
            p = cur / name
            info = entry_stat(p)
            if info is not None and stat.S_ISREG(info.st_mode):
                yield p.relative_to(root), info.st_size


def count_lines(path: Path):
    total = 0
    non_empty = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                total += 1
                if line.strip():
                    non_empty += 1
    except OSError:
        return 0, 0
    return total, non_empty


def detect_dependencies(root: Path):
    deps = {}
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8-sig"))
            deps["npm_dependencies"] = len(data.get("dependencies") or {})
            deps["npm_devDependencies"] = len(data.get("devDependencies") or {})
        except (OSError, ValueError):
            pass

    gomod = root / "go.mod"
    if gomod.is_file():
        try:
            in_block = False
            count = 0
            for raw in gomod.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.split("//", 1)[0].strip()
                if line == "require (":
                    in_block = True
                elif in_block and line == ")":
                    in_block = False
                elif in_block and line:
                    count += 1
                elif line.startswith("require ") and not line.endswith("("):
                    count += 1
            deps["go_requires"] = count
        except OSError:
            pass

    req = root / "requirements.txt"
    if req.is_file():
        try:
            lines = [
                l.strip() for l in req.read_text(encoding="utf-8", errors="replace").splitlines()
                if l.strip() and not l.strip().startswith(("#", "-"))
            ]
            deps["pip_requirements"] = len(lines)
        except OSError:
            pass

    cargo = root / "Cargo.toml"
    if cargo.is_file():
        try:
            in_deps = False
            count = 0
            for raw in cargo.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.split("#", 1)[0].strip()
                if line.startswith("["):
                    in_deps = line in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]")
                elif in_deps and "=" in line:
                    count += 1
            deps["cargo_dependencies"] = count
        except OSError:
            pass

    return deps


def detect_stacks(root: Path, by_ext: dict):
    stacks = []
    if (root / "package.json").is_file() or any(e in by_ext for e in (".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte")):
        stacks.append("node/web")
    if (root / "go.mod").is_file() or ".go" in by_ext:
        stacks.append("go")
    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file() or ".py" in by_ext:
        stacks.append("python")
    if (root / "Cargo.toml").is_file() or ".rs" in by_ext:
        stacks.append("rust")
    if (root / "pom.xml").is_file() or ".java" in by_ext or ".kt" in by_ext:
        stacks.append("java/jvm")
    return stacks


def build_snapshot(root: Path, top_n: int, max_files: int):
    info = entry_stat(root)
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"not a regular directory: {root}")

    by_ext = defaultdict(lambda: {"files": 0, "lines": 0, "non_empty_lines": 0})
    file_records = []
    files_scanned = 0
    truncated = False
    large_files = 0
    total_lines = 0
    total_non_empty = 0

    for rel, size in iter_project_files(root):
        name = rel.name.casefold()
        if name == ".git" or (name == ".env" or name.startswith(".env.")) and name not in {".env.example", ".env.sample", ".env.template"}:
            continue
        if files_scanned >= max_files:
            truncated = True
            break
        files_scanned += 1
        suffix = rel.suffix.casefold()
        if suffix not in SOURCE_SUFFIXES:
            continue
        lines, non_empty = count_lines(root / rel)
        total_lines += lines
        total_non_empty += non_empty
        if lines > 500:
            large_files += 1
        ext_stat = by_ext[suffix]
        ext_stat["files"] += 1
        ext_stat["lines"] += lines
        ext_stat["non_empty_lines"] += non_empty
        file_records.append({
            "path": rel.as_posix(),
            "lines": lines,
            "non_empty_lines": non_empty,
            "bytes": size,
        })

    file_records.sort(key=lambda r: (-r["lines"], r["path"]))
    sorted_ext = dict(sorted(by_ext.items(), key=lambda kv: (-kv[1]["lines"], kv[0])))
    stacks = detect_stacks(root, sorted_ext)
    deps = detect_dependencies(root)
    available_tools = {
        group: [tool for tool in tools if shutil.which(tool)]
        for group, tools in TOOL_PROBES.items()
    }
    quadrants = ["3_delivery", "4_complexity"]
    if "node/web" in stacks:
        quadrants.insert(0, "1_frontend_entry")
    if any(s in stacks for s in ("go", "python", "rust", "java/jvm", "node/web")):
        quadrants.insert(1 if "1_frontend_entry" in quadrants else 0, "2_service_data")

    return {
        "root": str(root),
        "files_scanned": files_scanned,
        "truncated": truncated,
        "stacks": stacks,
        "suggested_quadrants": quadrants,
        "summary": {
            "source_files": len(file_records),
            "total_lines": total_lines,
            "non_empty_lines": total_non_empty,
            "large_files_gt_500": large_files,
            "total_dependencies": sum(deps.values()),
            "by_extension": sorted_ext,
        },
        "top_files": file_records[:top_n],
        "dependencies": deps,
        "available_tools": available_tools,
    }


def compute_delta(before: dict, after: dict):
    b_sum = before.get("summary", {})
    a_sum = after.get("summary", {})
    keys = ("source_files", "total_lines", "non_empty_lines", "large_files_gt_500", "total_dependencies")
    return {k: a_sum.get(k, 0) - b_sum.get(k, 0) for k in keys}


def main():
    parser = argparse.ArgumentParser(description="Collect a deterministic project baseline snapshot for 0-optimize.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    parser.add_argument("--top", type=int, default=10, help="number of largest source files to list (default: 10)")
    parser.add_argument("--max-files", type=int, default=5000, help="max files to scan (default: 5000)")
    parser.add_argument("--out", type=Path, help="optional path to save snapshot JSON")
    parser.add_argument("--compare", type=Path, help="optional baseline JSON path to compute delta")
    args = parser.parse_args()

    try:
        snapshot = build_snapshot(args.root.resolve(strict=True), max(1, args.top), max(1, args.max_files))
        if args.compare:
            before = json.loads(args.compare.read_text(encoding="utf-8-sig"))
            snapshot["delta"] = compute_delta(before, snapshot)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
