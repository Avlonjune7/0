"""Check local Markdown file links and common GitHub-style heading anchors."""

import argparse
import html
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


LABEL = r"\[(?P<label>(?:\\.|[^\[\]\\\n]|\[[^\[\]\n]*\])*)\]"
DESTINATION = r"(?P<target><[^<>\n]*>|(?:\\.|[^\s()<>\\]|\((?:\\.|[^\s()\\])*\))*)"
TITLE = r"""(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?"""
INLINE = re.compile(r"(?<!\\)!?" + LABEL + r"\([ \t]*" + DESTINATION + TITLE + r"[ \t]*\)")
INLINE_START = re.compile(r"(?<!\\)!?" + LABEL + r"\(")
REFERENCE = re.compile(r"(?<!\\)!?" + LABEL + r"(?:\[(?P<reference>[^\[\]\n]*)\])?")
DEFINITION = re.compile(r"^ {0,3}" + LABEL + r":[ \t]*" + DESTINATION + TITLE + r"[ \t]*$")
DEFINITION_START = re.compile(r"^ {0,3}" + LABEL + ":")
FENCE = re.compile(r"^ {0,3}(\x60{3,}|~{3,})(.*)$")
INLINE_CODE = r"(?<![\\\x60])(\x60+)(?!\x60).*?(?<!\x60)\1(?!\x60)"
INLINE_CODE_OR_COMMENT = re.compile(INLINE_CODE + r"|<!--.*?(?:-->|$)", re.DOTALL)
ATX_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*?)|[ \t]*)$")
SETEXT_HEADING = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
EXPLICIT_ANCHOR = re.compile(
    r"""<[A-Za-z][^>\n]*?\s(?:id|name)\s*=\s*(['"])(.*?)\1[^>\n]*>""", re.IGNORECASE
)
PUNCTUATION_ESCAPE = re.compile(r"\\([!-/:-@\[-\x60{-~])")
LIMITS = (
    "Checks the listed Markdown files and opens linked Markdown targets only for anchors.",
    "Checks common inline and reference links, including image paths, with single-line destinations.",
    "Anchor checks use common GitHub-style ATX/Setext headings and quoted HTML id/name attributes.",
    "External URLs, HTML links, custom rendering, and advanced Markdown syntax are unverified.",
)


def blank(match):
    return re.sub(r"[^\r\n]", " ", match.group())


def prose_lines(content):
    """Return prose aligned to the input line numbers."""
    lines = []
    fence = None
    for line in content.splitlines():
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append("")
        elif marker:
            fence = marker[1]
            lines.append("")
        elif line.startswith(("    ", "\t")):
            lines.append("")
        else:
            lines.append(line)
    return INLINE_CODE_OR_COMMENT.sub(
        lambda match: match.group() if match[1] else blank(match), "\n".join(lines)
    ).split("\n")


def anchors(lines):
    result = set()
    plain = set()
    previous = ""
    for line in lines:
        anchor_line = INLINE_CODE_OR_COMMENT.sub(blank, line)
        for match in EXPLICIT_ANCHOR.finditer(anchor_line):
            result.add(html.unescape(match[2]))
        heading = ATX_HEADING.match(line)
        if heading:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading[1] or "")
        elif previous and SETEXT_HEADING.fullmatch(line):
            title = previous
        else:
            previous = line.strip()
            continue
        previous = ""
        title = INLINE.sub(lambda match: match["label"], title)
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"(?<!\w)(__?|[*~]+)(.+?)\1(?!\w)", r"\2", title)
        title = html.unescape(PUNCTUATION_ESCAPE.sub(r"\1", title)).strip().lower()
        slug = "".join(
            "-" if char in " \t" else char
            for char in title
            if char in " \t-_" or unicodedata.category(char)[0] in "LMN"
        )
        candidate = slug
        suffix = 1
        while candidate in plain:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        plain.add(candidate)
    return result | plain


def reference_key(value):
    return " ".join(value.split()).casefold()


def find_links(lines):
    lines = INLINE_CODE_OR_COMMENT.sub(blank, "\n".join(lines)).split("\n")
    definitions = {}
    body = []
    for line_no, line in enumerate(lines, 1):
        definition = DEFINITION.match(line)
        if definition:
            definitions.setdefault(reference_key(definition["label"]), definition["target"])
        elif DEFINITION_START.match(line):
            yield line_no, line.strip(), "unsupported reference definition"
        else:
            body.append((line_no, line))
    for line_no, line in body:
        for match in INLINE.finditer(line):
            yield line_no, match["target"], None
        remaining = INLINE.sub(blank, line)
        for match in INLINE_START.finditer(remaining):
            yield line_no, match.group(), "unsupported inline destination"
        remaining = INLINE_START.sub(blank, remaining)
        for match in REFERENCE.finditer(remaining):
            key = reference_key(match["reference"] or match["label"])
            if key in definitions:
                yield line_no, definitions[key], None
            elif match["reference"] is not None:
                yield line_no, match.group(), "reference definition not found"


def inspect_target(source, target, root, anchor_cache):
    target = html.unescape(PUNCTUATION_ESCAPE.sub(r"\1", target.strip("<>")))
    if re.match(r"^[A-Za-z]:[/\\]", target):
        return "unverified", "absolute drive path"
    try:
        url = urlsplit(target)
        if url.scheme or url.netloc:
            return "external", None
        path = unquote(url.path, errors="strict")
        fragment = unquote(url.fragment, errors="strict")
        if "\\" in path or "\x00" in path:
            return "unverified", "unsupported path separator or character"
        if path.startswith("/"):
            destination = (root / path.lstrip("/")).resolve()
        else:
            destination = (source.parent / path).resolve() if path else source
        if not destination.is_relative_to(root):
            return "unverified", "target outside the project root"
        destination.stat()
    except (FileNotFoundError, NotADirectoryError):
        return "broken", "target does not exist"
    except (OSError, ValueError, RuntimeError):
        return "unverified", "target could not be resolved or accessed"
    if not fragment:
        return "ok", None
    if not destination.is_file() or destination.suffix.lower() not in {".md", ".markdown"}:
        return "unverified", "anchor belongs to a non-Markdown target"
    if destination not in anchor_cache:
        try:
            anchor_cache[destination] = anchors(prose_lines(destination.read_text(encoding="utf-8-sig")))
        except (OSError, UnicodeError):
            return "unverified", "target Markdown could not be read as UTF-8"
    if fragment not in anchor_cache[destination]:
        return "broken", "Markdown anchor does not exist"
    return "ok", None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Exit 0: no broken links found. Exit 1: broken links. Exit 2: input error. "
        "Check the JSON unverified entries and limits for coverage gaps.",
    )
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(),
        help="project root (default: current directory), also used for links starting with /",
    )
    parser.add_argument("files", type=Path, nargs="+", help="Markdown files relative to --root or absolute")
    args = parser.parse_args()
    report = {"files": [], "checked": 0, "skipped_external": 0, "broken": [], "unverified": [],
              "input_errors": [], "limits": LIMITS}
    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError("project root must be a directory")
    except (OSError, ValueError, RuntimeError) as error:
        report["input_errors"].append({"file": str(args.root), "reason": str(error)})
    if not report["input_errors"]:
        documents = {}
        for supplied in args.files:
            try:
                source = (root / supplied).resolve(strict=True)
                if not source.is_relative_to(root) or source.suffix.lower() not in {".md", ".markdown"}:
                    raise ValueError("expected a Markdown file inside the project root")
                if source not in documents:
                    documents[source] = prose_lines(source.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError, RuntimeError) as error:
                report["input_errors"].append({"file": str(supplied), "reason": str(error)})
        anchor_cache = {source: anchors(lines) for source, lines in documents.items()}
        for source, lines in documents.items():
            path = source.relative_to(root).as_posix()
            report["files"].append(path)
            for line_no, target, reason in find_links(lines):
                status, reason = (
                    ("unverified", reason) if reason else inspect_target(source, target, root, anchor_cache)
                )
                if status == "external":
                    report["skipped_external"] += 1
                    continue
                if status in {"ok", "broken"}:
                    report["checked"] += 1
                if status in {"broken", "unverified"}:
                    report[status].append({"file": path, "line": line_no, "target": target, "reason": reason})
    print(json.dumps(report, ensure_ascii=True))
    return 2 if report["input_errors"] else int(bool(report["broken"]))


if __name__ == "__main__":
    raise SystemExit(main())
