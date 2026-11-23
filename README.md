# 0

个人技能集合，分为项目工作流与个人偏好两类，统一维护和同步。每个技能可以单独使用，沿用项目现有结构，不要求每次开发都走完整流程。

## 项目工作流：0-*

| 技能 | 用途 | 典型调用 |
| --- | --- | --- |
| [0-setup](skills/0-setup/SKILL.md) | 初始化 Git、建立文档入口、决策日志与约定，或集中核对并同步过期文档 | `$0-setup 初始化当前项目` |
| [0-plan](skills/0-plan/SKILL.md) | 查清现状、澄清需求，写出带 AC 编号的规格；中等以上任务经金鱼评审和批准 | `$0-plan 先规划这个功能，暂不实施` |
| [0-build](skills/0-build/SKILL.md) | 实施、排错、按 AC 验证；非小改收尾做金鱼代码评审，同步受影响文档 | `$0-build 按已确认的方案实现功能` |
| [0-review](skills/0-review/SKILL.md) | 用无历史的金鱼子代理审查规格或代码，核实问题与影响 | `$0-review 审查当前未提交变更` |
| [0-handoff](skills/0-handoff/SKILL.md) | 先判断是否需要交接，需要时保存任务状态供新会话继续 | `$0-handoff 为新窗口继续当前任务生成交接记录` |

五个技能都配置为手动触发（Codex 用 `agents/openai.yaml`，Claude Code 用 `disable-model-invocation`）。项目和用户指令优先；提交、推送、部署等外部操作按实际授权执行。0-plan 和 0-build 引用 0-review 的规则与脚本，五个技能需一起安装。

### 大象与金鱼

主会话是**大象**：持有项目上下文，负责规划和实施。**金鱼**是无会话历史的只读子代理，只拿到规格、原始需求和改动路径，用来发现大象看不到的隐含假设。**你**负责裁决取舍和批准规格。

```text
0-setup ─► 0-plan ─► [金鱼评审规格] ─► 你批准 ─► 0-build ─► [金鱼评审代码] ─► 交付
              ▲                                     │
              └──────── docs/decisions.md ◄──────────┘   （决策日志是大象的跨会话记忆）
```

- 规格状态 `草案 → 已批准`；验收条件编号 `AC-1…`，贯穿规格、验证和评审。
- 金鱼评审默认只做一轮，每个角度最多 5 条发现；小改跳过。
- 换窗口前用 0-handoff 先判断：能继续就继续，没用就新开，只有换工具、换目录、交给他人或分出支线时才写交接文件。

## 个人偏好：me-*

| 技能 | 用途 | 触发方式 |
| --- | --- | --- |
| [me-ui](skills/me-ui/SKILL.md) | 组件与设计系统、页面验收、浏览器与前端性能偏好 | 按任务匹配，也可手动调用 |
| [me-tools](skills/me-tools/SKILL.md) | CLI、Windows 路径、脚本检查及 Go 构建部署偏好 | 按任务匹配，也可手动调用 |

个人偏好包含作者的本机路径与工具选择，其他使用者可只安装 `0-*`。两类技能独立使用；工作流不要求安装个人技能，也不会自动安装其提及的工具。原 `me` 的有效内容已拆分到上述技能和已有工作流，旧同步脚本不再使用。本仓库的同步脚本不操作 CC Switch 或全局规则。

所有技能保持 `skills/<技能名>/` 的安装路径，通过本页分类导航。

## 使用方式

- 换窗口接续：先用 `0-handoff` 判断是否真的需要交接；需要时保存交接文件（默认项目根 `.handoff/`，本地排除不提交），再在新会话中读取。
- 接手项目或文档漂移核对：用 `0-setup` 建立必要文档入口，或在文档积累偏差时集中核对与同步；批准的需求与代码冲突时保留需求并报告差异，不把错误实现改写成正确规格。
- 明确的小修改：直接用 `0-build`，完成相关验证并顺手同步受影响文档。
- 复杂功能：用 `0-plan` 写规格和纵向切片，经金鱼评审和你批准后用 `0-build` 实施；单独复核已有设计或 PR 时调用 `0-review`。
- 想被深入追问时：对 `0-plan` 说"深挖"，它会一次问一个问题直到决策闭合。

`0-setup` 默认采用**轻量接入**（核对入口、配置、契约与已有文档，按需建立 `AGENTS.md`、`docs/workflow.md` 与根 `README`）；仅在明确要求全库模块建档或接手缺少说明的大中型代码库时启用**深度建档**，阈值与分块规则见 [deep-scan.md](skills/0-setup/references/deep-scan.md)。无法完整覆盖时明确报告缺口。

完整项目初始化时，`0-setup` 默认复用已有 Git，独立项目无仓库则初始化本地 `main` 并补齐必要忽略规则；局部或仅文档任务不自动初始化 Git。远端按明确需求和授权接入，不默认创建 GitHub 仓库、提交或推送。

其他技能仍按任务需要选择子代理。四个辅助脚本已在对应技能中提供按需指针，也可由使用者显式调用；目录扫描脚本不承担语法分块或代理调度。

## 安装到本地

按需将 `skills/` 下的技能目录放入个人技能目录。以下示例安装五个工作流技能；需要个人偏好时，将 `me-ui`、`me-tools` 加入 `$names`。适用于首次安装：

```powershell
git clone https://github.com/Avlonjune7/0.git
Set-Location 0

$destination = Join-Path $env:USERPROFILE '.codex\skills'
$names = '0-setup', '0-plan', '0-build', '0-review', '0-handoff'
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
| [check_links.py](skills/0-setup/scripts/check_links.py) | 检查指定 Markdown 的本地路径和常见标题锚点，列出未验证格式 |
| [run_checks.py](skills/0-build/scripts/run_checks.py) | 执行明确指定的验证命令，返回退出码、耗时和输出摘要；支持独立命令并发 |

```powershell
python skills/0-setup/scripts/scan_project.py --root D:/project/example
python skills/0-review/scripts/collect_changes.py --root D:/project/example
python skills/0-setup/scripts/check_links.py --root D:/project/example README.md docs/workflow.md
python skills/0-build/scripts/run_checks.py --root D:/project/example --commands checks.json --jobs 2
```

`checks.json` 是调用者选择并授权的命令清单，例如：

```json
[
  { "name": "单元测试", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"] },
  { "name": "差异格式检查", "argv": ["git", "diff", "--check"] }
]
```

仅将互不干扰的检查并发执行。`run_checks.py` 默认单命令超时 300 秒（可用 `--timeout` 调整或传 `0` 禁用，也可在清单项中单独设置 `timeout_sec`），仍应使用会自行结束的命令；退出码为零只表示命令通过，需求是否满足仍需验收。各脚本的 `--help` 提供完整参数。

## 修改后同步到 GitHub

同步入口为 [scripts/sync.ps1](scripts/sync.ps1)，需要 PowerShell、Git 和可用的 GitHub 推送凭据。仓库默认分支为 `main`。

**同步方向：本机已安装的七个技能 → 本仓库 `skills/` → GitHub。** 默认读取 `D:\DATA\cc switch\skills`，不会修改其他技能或全局 Git 配置。

```powershell
# 在仓库目录中预览变化，不修改文件或访问远端
.\scripts\sync.ps1 -Preview

# 修改本地技能后：同步、提交、推送
.\scripts\sync.ps1 -Message "完善审查流程"

# 从其他目录读取七个技能
.\scripts\sync.ps1 -SkillsRoot 'D:\my-skills' -Message "更新技能"

# 只同步并提交，暂不推送
.\scripts\sync.ps1 -NoPush -Message "本地更新"
```

若 Windows PowerShell 的执行策略阻止脚本，可只为本次进程运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync.ps1 -Message "更新技能"
```

脚本要求开始时工作区干净，只同步上述七个技能目录，并处理来源中已删除的对应文件。没有变化时不创建空提交；普通运行仍会推送已有本地提交。远端出现本地尚未包含的提交时停止，先检查并合并远端更新，再重新执行；不强制推送。

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

工作流借鉴 [Matt Pocock Skills](https://github.com/mattpocock/skills) 与 [Elephant–Goldfish Model](https://github.com/google/elephant-goldfish-model) 的需求澄清、实施验证、独立审查与文档维护思路，并按个人项目需求取舍。本仓库独立使用，不依赖安装这两套技能，也不是它们的官方发行版。技能正文不再重复来源说明，以本节为准。

| 0-* 环节 | 对应来源 |
| --- | --- |
| 0-setup 接入、深度建档、漂移核对 | Matt `setup-matt-pocock-skills`；EGM `egm-bootstrap`、`egm-drift-report` |
| 0-plan 澄清、深挖模式 | Matt `grill-me` / `grilling`；EGM `egm-brainstorm` |
| 0-plan 规格、AC、纵向切片 | Matt `to-spec`、`to-tickets`；EGM `egm-draft` |
| 0-plan 金鱼评审与批准 | EGM `egm-review`（可理解、实施就绪两个角度）、`egm-resolve` |
| 0-build 实施、TDD、排错 | Matt `implement`、`tdd`、`diagnosing-bugs`；EGM `egm-lite` |
| 0-build 收尾代码评审 / 0-review | Matt `code-review`（规格与规范双轴）；EGM `egm-lite` 对抗式 diff 评审 |
| 决策日志 | Matt `domain-modeling` 的 ADR，简化为单文件追加 |
| 0-handoff 阶段边界判断与交接 | Matt `handoff`、`ask-matt` 的 PHASE-BOUNDARIES |
| 交付末尾的一条改进建议 | Matt `retro`，简化为单条建议 |

有意未纳入：triage、wayfinder、implement-spec、pr、wizard、teach 和 EGM 完整五阶段评审流水线，它们主要面向团队协作或超大任务。
