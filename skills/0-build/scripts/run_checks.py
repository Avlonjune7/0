#!/usr/bin/env python3
"""Run explicitly selected project checks and report their actual results."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import time


TAIL_BYTES = 8192


@dataclass(frozen=True)
class Check:
    name: str
    argv: list[str]
    cwd: Path


def valid_text(value):
    return isinstance(value, str) and bool(value.strip()) and "\0" not in value


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_checks(manifest, root):
    with manifest.open(encoding="utf-8-sig") as source:
        items = json.load(source, object_pairs_hook=unique_keys)
    if not isinstance(items, list) or not items:
        raise ValueError("the manifest must contain a nonempty array of checks")

    checks = []
    names = set()
    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict) or item.keys() - {"name", "argv", "cwd"}:
            raise ValueError(f"check {position} accepts only name, argv and optional cwd")

        name = item.get("name")
        if not valid_text(name) or name in names:
            raise ValueError(f"check {position} requires a unique, nonblank name")

        argv = item.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or not valid_text(argv[0])
            or any(not isinstance(arg, str) or "\0" in arg for arg in argv)
        ):
            raise ValueError(f"check {name!r} requires argv with an executable and string arguments")
        if os.name == "nt" and Path(argv[0].rstrip(" .")).suffix.lower() in {".bat", ".cmd"}:
            raise ValueError(f"check {name!r} must invoke cmd.exe explicitly for a batch file")

        cwd_value = item.get("cwd", ".")
        if not valid_text(cwd_value):
            raise ValueError(f"check {name!r} requires a nonblank cwd path")
        cwd = (root / cwd_value).resolve()
        if not cwd.is_relative_to(root) or not cwd.is_dir():
            raise ValueError(f"check {name!r} requires an existing directory under --root")

        if os.path.dirname(argv[0]) and not Path(argv[0]).is_absolute():
            argv = [str(cwd / argv[0]), *argv[1:]]
        checks.append(Check(name, argv, cwd))
        names.add(name)
    return checks


def run_check(check):
    start = time.monotonic()
    output_tail = bytearray()
    truncated = False
    exit_code = None
    launch_error = None

    try:
        process = subprocess.Popen(
            check.argv,
            cwd=check.cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    except OSError as exc:
        launch_error = str(exc)
    else:
        with process:
            while chunk := process.stdout.read1(TAIL_BYTES):
                output_tail.extend(chunk)
                if len(output_tail) > TAIL_BYTES:
                    del output_tail[:-TAIL_BYTES]
                    truncated = True
            exit_code = process.wait()

    return {
        "name": check.name,
        "cwd": str(check.cwd),
        "exit_code": exit_code,
        "duration_ms": round((time.monotonic() - start) * 1000),
        "launch_error": launch_error,
        "output_tail": output_tail.decode("utf-8", errors="replace"),
        "output_truncated": truncated,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run caller-selected, authorized project verification commands.",
        epilog=(
            'Manifest format: [{"name":"unit tests","argv":["python","-m","unittest"],'
            '"cwd":"backend"}]. Provide argv as argument strings. On Windows use an '
            'explicit cmd.exe argv for .bat or .cmd commands. Only select checks that '
            'exit on their own. The JSON report includes the last 8192 bytes of combined '
            'stdout/stderr per check, decoded as UTF-8. Exit 0 means all commands '
            'returned zero, 1 means a command failed or could not launch, and 2 means invalid input.'
        ),
    )
    parser.add_argument("--root", type=Path, required=True, help="project root and default cwd")
    parser.add_argument("--commands", type=Path, required=True, help="path to the UTF-8 JSON manifest")
    parser.add_argument(
        "--jobs", type=int, default=1,
        help="maximum concurrent checks (default: 1). Use a higher value only for independent checks.",
    )
    args = parser.parse_args()

    try:
        if args.jobs < 1:
            raise ValueError("--jobs must be at least 1")
        root = args.root.resolve()
        if not root.is_dir():
            raise ValueError("--root must be an existing directory")
        checks = load_checks(args.commands, root)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}))
        return 2

    jobs = min(args.jobs, len(checks))
    if jobs == 1:
        results = [run_check(check) for check in checks]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            results = list(executor.map(run_check, checks))

    passed = all(result["exit_code"] == 0 for result in results)
    print(json.dumps({"status": "passed" if passed else "failed", "results": results}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
