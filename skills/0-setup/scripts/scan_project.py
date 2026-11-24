"""Collect project paths without reading file contents."""

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess


SKIP_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "vendor", "__pycache__",
    ".next", ".nuxt", ".pytest_cache", "build", "dist", "coverage", "target",
}
DOCUMENT_SUFFIXES = {".md", ".mdx", ".rst", ".adoc"}
DOCUMENT_NAMES = {"readme", "license", "changelog", "authors", "contributing"}
CONFIG_NAMES = {
    ".editorconfig", ".env.example", ".env.sample", ".env.template",
    ".gitignore", ".pre-commit-config.yaml", "cargo.toml", "cargo.lock", "cmakelists.txt",
    "composer.json", "composer.lock", "dockerfile", "go.mod", "go.sum", "gradlew",
    "makefile", "gemfile", "gemfile.lock", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "pnpm-workspace.yaml", "pom.xml", "pyproject.toml", "pytest.ini",
    "requirements.txt", "setup.cfg", "setup.py", "uv.lock", "yarn.lock", "meson.build",
    "tsconfig.json", "jsconfig.json", "deno.json", "deno.jsonc", "pubspec.yaml",
}
CONFIG_PREFIXES = (
    "compose.", "docker-compose.", "dockerfile.", "build.gradle", "settings.gradle",
    "eslint.config.", "prettier.config.", "vite.config.", "vitest.config.",
    "jest.config.", "playwright.config.", "next.config.", "tsconfig.", "requirements-",
)
SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".dart", ".ex", ".exs", ".fs", ".go", ".h", ".hpp",
    ".java", ".js", ".jsx", ".kt", ".lua", ".mjs", ".cjs", ".php", ".py", ".rb",
    ".rs", ".scala", ".sh", ".ps1", ".sql", ".svelte", ".swift", ".ts", ".tsx", ".vue",
}


def entry_stat(path):
    try:
        info = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return None
    if stat.S_ISLNK(info.st_mode):
        return None
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return None
    return info


def git_paths(root, raw_paths):
    seen = set()
    checked_dirs = {}
    for raw_path in raw_paths.split(b"\0"):
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        relative = Path(os.fsdecode(raw_path))
        if relative.anchor or ".." in relative.parts:
            continue
        if any(directory.casefold() in SKIP_DIRECTORIES for directory in relative.parts[:-1]):
            continue
        current = root
        dir_ok = True
        for part in relative.parts[:-1]:
            current = current / part
            ok = checked_dirs.get(current)
            if ok is None:
                ok = entry_stat(current) is not None
                checked_dirs[current] = ok
            if not ok:
                dir_ok = False
                break
        if not dir_ok:
            continue
        info = entry_stat(current / relative.parts[-1])
        if info is not None and stat.S_ISREG(info.st_mode):
            yield relative


def _is_reparse_or_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def walk_paths(root):
    def _walk(current):
        with os.scandir(current) as it:
            entries = sorted(it, key=lambda e: e.name)
        dirs = []
        for entry in entries:
            try:
                info = entry.stat(follow_symlinks=False)
            except (FileNotFoundError, NotADirectoryError):
                continue
            if _is_reparse_or_link(info):
                continue
            if stat.S_ISDIR(info.st_mode):
                if entry.name.casefold() not in SKIP_DIRECTORIES:
                    dirs.append(Path(entry.path))
            elif stat.S_ISREG(info.st_mode):
                yield Path(entry.path).relative_to(root)
        for sub in dirs:
            yield from _walk(sub)

    yield from _walk(root)


GIT_REPO_ENV_VARS = {
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
}


def scan(root, max_files):
    info = entry_stat(root)
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"not a regular directory: {root}")
    exclusions = [f"--exclude={directory}/" for directory in sorted(SKIP_DIRECTORIES)]
    git_env = {k: v for k, v in os.environ.items() if k not in GIT_REPO_ENV_VARS}
    git_env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard",
             *exclusions, "--"],
            env=git_env,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        fallback = f"cannot run git: {error}"
    else:
        fallback = None if listing.returncode == 0 else listing.stderr.decode("utf-8", "replace").strip()
        if listing.returncode and not fallback:
            fallback = f"git ls-files exited {listing.returncode}"

    paths = walk_paths(root) if fallback is not None else git_paths(root, listing.stdout)
    documents = []
    configs = []
    source_dirs = set()
    file_count = 0
    truncated = False

    for path in paths:
        name = path.name.casefold()
        is_private_env = (name == ".env" or name.startswith(".env.")) and name not in CONFIG_NAMES
        if name == ".git" or is_private_env:
            continue
        if file_count == max_files:
            truncated = True
            break
        file_count += 1
        suffix = path.suffix.casefold()
        if suffix in DOCUMENT_SUFFIXES or name in DOCUMENT_NAMES:
            documents.append(path.as_posix())
        elif name in CONFIG_NAMES or name.startswith(CONFIG_PREFIXES) or path.parts[:2] == (".github", "workflows"):
            configs.append(path.as_posix())
        elif suffix in SOURCE_SUFFIXES:
            source_dirs.add(path.parent.as_posix())

    return {
        "root": str(root),
        "scan_method": "filesystem" if fallback is not None else "git",
        "git_fallback_reason": fallback,
        "max_files": max_files,
        "files_scanned": file_count,
        "truncated": truncated,
        "documents": sorted(documents),
        "configurations": sorted(configs),
        "candidate_source_dirs": sorted(source_dirs),
    }


def main():
    parser = argparse.ArgumentParser(
        description=("List project documents, common configuration paths, and directories containing source "
                     "files as JSON. Uses Git's tracked and nonignored untracked paths when available, "
                     "otherwise walks the requested directory. Skips links, junctions, and common output "
                     "directories. Reads filenames only. Source directories are candidates by extension."),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="directory to scan (default: current directory)")
    parser.add_argument("--max-files", type=int, default=2000, help="maximum eligible files to classify (default: 2000)")
    args = parser.parse_args()
    if args.max_files < 1:
        parser.error("--max-files must be positive")
    try:
        report = scan(Path(os.path.abspath(args.root)), args.max_files)
    except (OSError, ValueError) as error:
        parser.exit(2, f"{error}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
