# 0

个人技能集合，分为项目工作流与个人偏好两类，统一维护和同步。每个技能可以单独使用，沿用项目现有结构，不要求每次开发都走完整流程。

## 项目工作流：0-*

| 技能 | 用途 | 典型调用 |
| --- | --- | --- |
| [0-setup](skills/0-setup/SKILL.md) | 初始化 Git、调查项目，建立或补齐文档入口与工作约定 | `$0-setup 初始化当前项目` |
| [0-plan](skills/0-plan/SKILL.md) | 查清现状、澄清需求、形成方案与验收条件 | `$0-plan 先规划这个功能，暂不实施` |
| [0-build](skills/0-build/SKILL.md) | 实施功能、定位缺陷、验证并同步受影响文档 | `$0-build 按已确认的方案实现功能` |
| [0-review](skills/0-review/SKILL.md) | 审查设计或代码，核实问题与影响 | `$0-review 审查当前未提交变更` |
| [0-sync](skills/0-sync/SKILL.md) | 核对文档与实现，修订有依据的过期说明 | `$0-sync 检查并同步本次改动影响的文档` |
| [0-handoff](skills/0-handoff/SKILL.md) | 保存当前任务状态，交接到新聊天继续 | `$0-handoff 为新窗口继续当前任务生成交接记录` |
| [0-retro](skills/0-retro/SKILL.md) | 基于开发过程复盘返工与低效，提出最小改进 | `$0-retro 复盘这次开发，先给建议` |

七个技能都配置为手动触发。项目和用户指令优先；提交、推送、部署等外部操作按实际授权执行。

## 个人偏好：me-*

| 技能 | 用途 | 触发方式 |
| --- | --- | --- |
| [me-ui](skills/me-ui/SKILL.md) | 组件与设计系统、页面验收、浏览器与前端性能偏好 | 按任务匹配，也可手动调用 |
| [me-tools](skills/me-tools/SKILL.md) | CLI、Windows 路径、脚本检查及 Go 构建部署偏好 | 按任务匹配，也可手动调用 |

个人偏好包含作者的本机路径与工具选择，其他使用者可只安装 `0-*`。两类技能独立使用；工作流不要求安装个人技能，也不会自动安装其提及的工具。原 `me` 的有效内容已拆分到上述技能和已有工作流，旧同步脚本不再使用。本仓库的同步脚本不操作 CC Switch 或全局规则。

所有技能保持 `skills/<技能名>/` 的安装路径，通过本页分类导航。

## 使用方式

- 换窗口接续：用 `0-handoff` 保存交接记录，再在同一实际工作目录的新聊天中读取；已有任务记录优先复用，否则保存到系统临时目录。
- 发生明显返工或重复排错：用 `0-retro` 基于原开发记录复盘，默认只给建议，不自动修改规则或配置。
- 接手项目：用 `0-setup` 建立必要文档入口。
- 明确的小修改：直接用 `0-build`，完成相关验证。
- 复杂功能：用 `0-plan` 明确方案，再用 `0-build` 实施；需要独立复核时调用 `0-review`。
- 文档积累了偏差：用 `0-sync` 集中核对。批准的需求与代码冲突时保留需求并报告差异，不把错误实现改写成正确规格。

`0-setup` 必须将源码按完整函数、类或方法边界分块，每块目标约 1,500 行；主会话通过宿主原生子代理能力组织独立上下文阅读，多个独立块并发处理，最多同时 6 个阅读子代理。已有 README 也要重新核对源码，汇总模块事实后自底向上逐层生成文档。无法满足独立阅读时明确报告缺口。

完整项目初始化时，`0-setup` 默认复用已有 Git，独立项目无仓库则初始化本地 `main` 并补齐必要忽略规则；局部或仅文档任务不自动初始化 Git。远端按明确需求和授权接入，不默认创建 GitHub 仓库、提交或推送。

其他技能仍按任务需要选择子代理。辅助脚本需要代理或使用者显式调用；目录扫描脚本不承担语法分块或代理调度。

## 安装到本地

按需将 `skills/` 下的技能目录放入个人技能目录。以下示例安装七个工作流技能；需要个人偏好时，将 `me-ui`、`me-tools` 加入 `$names`。适用于首次安装：

```powershell
git clone https://github.com/Avlonjune7/0.git
Set-Location 0

$destination = Join-Path $env:USERPROFILE '.agents\skills'
$names = '0-setup', '0-plan', '0-build', '0-review', '0-sync', '0-handoff', '0-retro'
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

其他系统可复制到宿主支持的技能目录。工作流技能的手动触发配置位于其 `agents/openai.yaml`；是否支持此配置，以所用宿主为准。

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

**同步方向：本机已安装的九个技能 → 本仓库 `skills/` → GitHub。** 默认读取 `$env:USERPROFILE\.agents\skills`，不会修改其他技能或全局 Git 配置。

```powershell
# 在仓库目录中预览变化，不修改文件或访问远端
.\scripts\sync.ps1 -Preview

# 修改本地技能后：同步、提交、推送
.\scripts\sync.ps1 -Message "完善审查流程"

# 从其他目录读取九个技能
.\scripts\sync.ps1 -SkillsRoot 'D:\my-skills' -Message "更新技能"

# 只同步并提交，暂不推送
.\scripts\sync.ps1 -NoPush -Message "本地更新"
```

若 Windows PowerShell 的执行策略阻止脚本，可只为本次进程运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync.ps1 -Message "更新技能"
```

脚本要求开始时工作区干净，只同步上述九个技能目录，并处理来源中已删除的对应文件。没有变化时不创建空提交；普通运行仍会推送已有本地提交。远端出现本地尚未包含的提交时停止，先检查并合并远端更新，再重新执行；不强制推送。

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
