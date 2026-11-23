"""Exercise the Markdown link checker through its command-line interface."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "skills" / "0-setup" / "scripts" / "check_links.py"


class CheckLinksTest(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory()
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name) / "project"
        self.root.mkdir()

    def write(self, file, content=""):
        path = self.root / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_checker(self, *files):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), *files],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def test_common_links_and_anchors(self):
        tick = chr(96)
        self.write(
            "docs/项目 指南.md",
            f"# 使用 _说明_\n\n# 重复\n\n## 重复\n\n设置\n---\n\n# 命令 {tick}git_status{tick}\n",
        )
        self.write("docs/example (1).txt")
        self.write("docs/图.svg")
        self.write("README.md", """# 自身示例

<a id="manual-anchor"></a>
[本文](#%E8%87%AA%E8%BA%AB%E7%A4%BA%E4%BE%8B)
[指南](docs/项目%20指南.md#使用-说明)
[引用][GUIDE]
[另一个][]
[GUIDE]
[锚点](#manual-anchor)
[示例](docs/example%20(1).txt)
![图](/docs/图.svg)
[命令](docs/项目%20指南.md#命令-git_status)
[外链](https://example.invalid)

[guide]: <docs/项目 指南.md#重复-1> "指南"
[另一个]: docs/项目%20指南.md#设置
""")
        code, report = self.run_checker("README.md")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["checked"], 9, report)
        self.assertEqual(report["skipped_external"], 1)
        self.assertEqual(report["unverified"], [])

    def test_broken_and_unverified_targets(self):
        self.write("target.md", "# Existing")
        self.write("outside.md", "# Outside")
        self.write("source.py")
        self.write("README.md", """[Missing](absent.md)
[Bad anchor](target.md#absent)
[Line reference](source.py#L1)
[Outside](../outside.md)
[Strange](one two.md)
[Other][missing-reference]
""")
        code, report = self.run_checker("README.md")
        self.assertEqual(code, 1, report)
        self.assertEqual([item["line"] for item in report["broken"]], [1, 2])
        self.assertEqual([item["line"] for item in report["unverified"]], [3, 4, 5, 6])
        self.assertEqual(report["unverified"][-1]["reason"], "reference definition not found")

    def test_code_comments_and_external_handles_are_skipped(self):
        self.write("README.md", """~~~~md
# Ghost
[fenced](absent.md)
~~~~

""" + chr(96) + "[inline](absent.md) <!--" + chr(96) + """

    [indented](absent.md)

<!-- [comment](absent.md) -->
[Remote](//example.invalid/foo.md)
[Real](README.md)
[Ignored heading](#ghost)
""")
        code, report = self.run_checker("README.md")
        self.assertEqual(code, 1, report)
        self.assertEqual(report["checked"], 2)
        self.assertEqual(report["skipped_external"], 1)
        self.assertEqual([item["target"] for item in report["broken"]], ["#ghost"])
        self.assertEqual(report["unverified"], [])

    def test_missing_input_returns_input_error(self):
        self.write("README.md", "[Self](README.md)")
        code, report = self.run_checker("README.md", "missing.md")
        self.assertEqual(code, 2, report)
        self.assertEqual(report["files"], ["README.md"])
        self.assertEqual(report["checked"], 1)
        self.assertEqual(report["input_errors"][0]["file"], "missing.md")

    def test_invalid_utf8_input_and_anchor_are_reported(self):
        (self.root / "invalid.md").write_bytes(b"# \xff")
        self.write("README.md", "[Invalid encoding](invalid.md#test)")
        code, report = self.run_checker("README.md", "invalid.md")
        self.assertEqual(code, 2, report)
        self.assertEqual(report["input_errors"][0]["file"], "invalid.md")
        self.assertEqual(report["unverified"][0]["reason"], "target Markdown could not be read as UTF-8")

    def test_fence_inside_html_comment_does_not_hide_following_broken_links(self):
        self.write("README.md", "<!--\n```\n-->\n[Broken](missing.md)\n")
        code, report = self.run_checker("README.md")
        self.assertEqual(code, 1, report)
        self.assertEqual([item["target"] for item in report["broken"]], ["missing.md"])


if __name__ == "__main__":
    unittest.main()
