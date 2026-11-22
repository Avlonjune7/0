# 0

一套面向个人项目的轻量开发技能：建立文档、规划变更、实施、审查和同步文档。每个技能可以单独使用，沿用项目现有结构，不要求每次开发都走完整流程。

## 五个技能

| 技能 | 用途 | 典型调用 |
| --- | --- | --- |
| [0-setup](skills/0-setup/SKILL.md) | 调查项目，建立或补齐文档入口与工作约定 | `$0-setup 为当前项目补齐必要文档` |
| [0-plan](skills/0-plan/SKILL.md) | 查清现状、澄清需求、形成方案与验收条件 | `$0-plan 先规划这个功能，暂不实施` |
| [0-build](skills/0-build/SKILL.md) | 实施功能、定位缺陷、验证并同步受影响文档 | `$0-build 按已确认的方案实现功能` |
| [0-review](skills/0-review/SKILL.md) | 审查设计或代码，核实问题与影响 | `$0-review 审查当前未提交变更` |
| [0-sync](skills/0-sync/SKILL.md) | 核对文档与实现，修订有依据的过期说明 | `$0-sync 检查并同步本次改动影响的文档` |

五个技能都配置为手动触发。项目和用户指令优先；提交、推送、部署等外部操作按实际授权执行。

## 使用方式

- 接手项目：用 `0-setup` 建立必要文档入口。
- 明确的小修改：直接用 `0-build`，完成相关验证。
- 复杂功能：用 `0-plan` 明确方案，再用 `0-build` 实施；需要独立复核时调用 `0-review`。
- 文档积累了偏差：用 `0-sync` 集中核对。批准的需求与代码冲突时保留需求并报告差异，不把错误实现改写成正确规格。

技能内已有按任务选择子代理的指导，实际并发取决于宿主能力与任务划分。**当前版本没有强制多代理调度器，也没有把下方辅助脚本自动接入技能流程。** 脚本需要代理或使用者显式调用。

## 安装到本地

将本仓库的五个 `skills/0-*` 目录分别放入个人技能目录。以下为 Windows PowerShell 示例，适用于首次安装：

```powershell
git clone https://github.com/Avlonjune7/0.git
Set-Location 0

$destination = Join-Path $env:USERPROFILE '.agents\skills'
$names = '0-setup', '0-plan', '0-build', '0-review', '0-sync'
foreach ($name in $names) {
    if (Test-Path -LiteralPath (Join-Path $destination $name)) {
        throw "已有 $name，请先比对本地修改后再更新。"
    }
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($name in $names) {
    Copy-Item -LiteralPath (Join-Path 'skills' $name) -Destination $destination -Recurse
}
```

其他系统可复制到宿主支持的技能目录。手动触发配置位于各技能的 `agents/openai.yaml`；是否支持此配置，以所用宿主为准。

## 辅助脚本

Python 脚本只依赖标准库，使用 Python 3.10 或更高版本。Git 变更收集需要 Git；目录扫描在 Git 不可用时退回文件系统扫描。以下命令从本仓库根目录执行，`python` 可替换为本机 Python 可执行文件路径。

| 脚本 | 功能 |
| --- | --- |
| [scan_project.py](skills/0-setup/scripts/scan_project.py) | 列出文档、配置、候选源码目录，标明扫描方式与截断情况 |
| [collect_changes.py](skills/0-review/scripts/collect_changes.py) | 分开收集暂存、未暂存、未跟踪文件，或比较固定提交 |
| [check_links.py](skills/0-sync/scripts/check_links.py) | 检查指定 Markdown 的本地路径和常见标题锚点，列出未验证格式 |
| [run_checks.py](skills/0-build/scripts/run_checks.py) | 执行明确指定的验证命令，返回退出码、耗时和输出摘要；支持独立命令并发 |

```powershell
python skills/0-setup/scripts/scan_project.py --root D:/project/example
python skills/0-review/scripts/collect_changes.py --root D:/project/example
python skills/0-sync/scripts/check_links.py --root D:/project/example README.md docs/workflow.md
python skills/0-build/scripts/run_checks.py --root D:/project/example --commands checks.json --jobs 2
```

`checks.json` 是调用者选择并授权的命令清单，例如：

```json
[
  { "name": "单元测试", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"] },
  { "name": "差异格式检查", "argv": ["git", "diff", "--check"] }
]
```

仅将互不干扰的检查并发执行。验证执行器目前没有超时控制，应使用会自行结束的命令；退出码为零只表示命令通过，需求是否满足仍需验收。各脚本的 `--help` 提供完整参数。

## 修改后同步到 GitHub

同步入口为 [scripts/sync.ps1](scripts/sync.ps1)，需要 PowerShell、Git 和可用的 GitHub 推送凭据。仓库默认分支为 `main`。

**同步方向：本机已安装的五个技能 → 本仓库 `skills/` → GitHub。** 默认读取 `$env:USERPROFILE\.agents\skills`，不会修改其他技能或全局 Git 配置。

```powershell
# 在仓库目录中预览变化，不修改文件或访问远端
.\scripts\sync.ps1 -Preview

# 修改本地技能后：同步、提交、推送
.\scripts\sync.ps1 -Message "完善审查流程"

# 从其他目录读取五个技能
.\scripts\sync.ps1 -SkillsRoot 'D:\my-skills' -Message "更新技能"

# 只同步并提交，暂不推送
.\scripts\sync.ps1 -NoPush -Message "本地更新"
```

若 Windows PowerShell 的执行策略阻止脚本，可只为本次进程运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync.ps1 -Message "更新技能"
```

脚本要求开始时工作区干净，只同步五个技能目录，并处理来源中已删除的对应文件。没有变化时不创建空提交；普通运行仍会推送已有本地提交。远端出现本地尚未包含的提交时停止，先检查并合并远端更新，再重新执行；不强制推送。

README、测试或同步脚本本身的修改直接在仓库中维护，先自行检查并提交，再运行同步脚本。不要同时把安装目录和仓库副本当作技能的编辑来源：默认以本机安装目录为准。

## 验证脚本

仓库保存了四个 Python 工具的回归测试：

```powershell
python -B -m unittest discover -s tests -v
```

同步上传脚本另有本地集成测试，不访问 GitHub：

```powershell
.\tests\test_sync_upload.ps1
```

测试通过临时项目和本地 Git 仓库验证实际行为；符号链接和目录联接测试在系统权限不足时会跳过。同步脚本已在 Windows PowerShell 5.1 和 PowerShell 7 验证，Python 工具已在 Windows 验证；其他操作系统尚未实测。

## 方法参考

工作流借鉴 [Matt Pocock Skills](https://github.com/mattpocock/skills) 与 [Elephant–Goldfish Model](https://github.com/google/elephant-goldfish-model) 的需求澄清、实施验证、独立审查与文档维护思路，并按个人项目需求取舍。本仓库独立使用，不依赖安装这两套技能，也不是它们的官方发行版。
