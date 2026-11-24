# 0

个人技能集合，分为 **项目工作流（`0-*`，6 个）** 与 **个人偏好（`me-*`，2 个）** 两类。每个技能均可独立使用，沿用项目现有结构，不要求每次开发都走完整流程。

## 快速安装与触发

将 `skills/` 下的目录复制到对应工具的技能目录（或软链接）：

- **Codex / Claude Code / Antigravity**：全局技能目录通常为 `~/.codex/skills/`、`~/.claude/skills/` 或 `~/.gemini/config/skills/`。
- **`0-*` 工作流**：均为手动触发（Codex 用 `$0-xxx`；Antigravity / Claude Code 用 `/0-xxx`）。
- **`me-*` 偏好**：按任务自动匹配，也可手动调用。

> `0-plan` 与 `0-build` 会引用 `0-review` 的规则与脚本，安装工作流时建议 `0-*` 六个一起安装；其他使用者可只安装 `0-*`，跳过含本机路径偏好的 `me-*`。

---

## 项目工作流：`0-*`

| 技能 | 用途 | 典型调用 |
| --- | --- | --- |
| [0-setup](skills/0-setup/SKILL.md) | 初始化 Git、建立文档入口、决策日志与约定，或集中核对并同步过期文档 | `/0-setup 初始化当前项目` |
| [0-plan](skills/0-plan/SKILL.md) | 查明现状、澄清需求，写出带 AC 编号的规格；中等以上任务经金鱼评审和批准 | `/0-plan 先规划这个功能，暂不实施` |
| [0-build](skills/0-build/SKILL.md) | 实施、排错、按 AC 验证；非小改收尾做金鱼代码评审，同步受影响文档 | `/0-build 按已确认的方案实现功能` |
| [0-review](skills/0-review/SKILL.md) | 用无历史的金鱼子代理审查规格或代码，核实问题与影响 | `/0-review 审查当前未提交变更` |
| [0-handoff](skills/0-handoff/SKILL.md) | 先判断是否需要交接，需要时保存任务状态供新会话继续 | `/0-handoff 为新窗口继续当前任务生成交接记录` |
| [0-learn](skills/0-learn/SKILL.md) | 复盘本会话纠正与排障根因，按严格落点路由提议沉淀到 `me-*` 或项目文档 | `/0-learn 复盘并沉淀本次经验` |

### 大象与金鱼 + `0-learn` 闭环

主会话是**大象**（持有项目上下文，负责规划和实施）；**金鱼**是无会话历史的只读子代理（仅拿规格、原始需求和改动路径，用于发现隐含假设）；**你**负责裁决取舍与批准规格。

```text
0-setup ─► 0-plan ─► [金鱼评审规格] ─► 你批准 ─► 0-build ─► [金鱼评审代码] ─► 交付 ─► 0-learn
              ▲                                                                           │
              └─────────────────── docs/decisions.md ◄────────────────────────────────────┘
                                   me-tools / me-ui  ◄──（跨项目通用经验回写个人偏好）
```

- 规格状态 `草案 → 已批准`；验收条件编号 `AC-1…`，贯穿规格、验证和评审。
- 金鱼评审默认只做一轮，每个角度最多 5 条发现；明确小改可直接跳过。

---

## 个人偏好：`me-*`

| 技能 | 用途 | 触发方式 |
| --- | --- | --- |
| [me-ui](skills/me-ui/SKILL.md) | 组件与设计系统、页面验收、浏览器与前端性能偏好 | 按任务匹配，也可手动调用 |
| [me-tools](skills/me-tools/SKILL.md) | CLI、Windows PATH 与脚本执行排障、RTK、静态检查、Go 与 Android 便携构建偏好 | 按任务匹配，也可手动调用 |

---

## 场景速查

- **接手项目或文档漂移**：`0-setup`（默认轻量接入；需要全库建档或核对漂移时按提示启用对应模式）。
- **明确的小修改**：直接 `0-build`，完成验证并同步受影响文档。
- **复杂功能**：`0-plan` 写规格与纵向切片（说「深挖」可逐个追问直到决策闭合）→ 评审批准 → `0-build` 实施。
- **独立复核 PR / 设计**：`0-review`。
- **换窗口接续**：先跑 `0-handoff` 判断是否真需要交接；需要时默认写 `.handoff/`（本地排除不提交）。
- **做完复盘沉淀**：`0-learn` 自动分流——跨项目工具/UI 经验回写 `me-*`，单项目约束/决定回写 `AGENTS.md` / `GEMINI.md` / `docs/decisions.md`。

---

<details>
<summary>辅助脚本与 checks.json（4 个独立 Python 工具）</summary>

- `skills/0-setup/scripts/scan_project.py`：扫描项目文档、配置与候选源码目录
- `skills/0-setup/scripts/check_links.py`：批量校验 Markdown 本地相对链接
- `skills/0-review/scripts/collect_changes.py`：收集待审查变更
- `skills/0-build/scripts/run_checks.py`：并发执行授权的检查清单（默认单命令超时 300s）

```powershell
python skills/0-setup/scripts/scan_project.py --root D:/project/example
python skills/0-review/scripts/collect_changes.py --root D:/project/example
python skills/0-setup/scripts/check_links.py --root D:/project/example README.md docs/workflow.md
python skills/0-build/scripts/run_checks.py --root D:/project/example --commands checks.json --jobs 2
```

`checks.json` 示例：

```json
[
  { "name": "单元测试", "argv": ["python", "-m", "unittest", "discover", "-s", "tests"] },
  { "name": "差异格式检查", "argv": ["git", "diff", "--check"] }
]
```

</details>

<details>
<summary>同步到 GitHub 与仓库回归测试（scripts/sync.ps1）</summary>

同步方向：**本机已安装的 8 个技能 → 本仓库 `skills/` → GitHub `main`**（默认读取 `D:\DATA\cc switch\skills`）。

```powershell
.\scripts\sync.ps1 -Preview                          # 预览变化，不改文件、不推远端
.\scripts\sync.ps1 -Message "完善审核流程"           # 同步、提交并推送
.\scripts\sync.ps1 -SkillsRoot 'D:\my-skills'        # 指定来源目录
.\scripts\sync.ps1 -NoPush -Message "本地更新"       # 只同步并提交，暂不推送
```

若 PowerShell 执行策略阻止脚本，可单次绕过：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync.ps1 -Message "更新技能"
```

回归测试：

```powershell
python -B -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\test_sync_upload.ps1
```

</details>

<details>
<summary>方法参考（Matt Pocock Skills & Elephant–Goldfish Model）</summary>

工作流借鉴 [Matt Pocock Skills](https://github.com/mattpocock/skills) 与 [Elephant–Goldfish Model](https://github.com/google/elephant-goldfish-model) 的需求澄清、实施验证、独立审查与文档维护思路，并按个人项目需求取舍；本仓库独立使用，不依赖安装这两套技能。

| `0-*` 环节 | 对应来源 |
| --- | --- |
| `0-setup` 接入、深度建档、漂移核对 | Matt `setup-matt-pocock-skills`；EGM `egm-bootstrap`、`egm-drift-report` |
| `0-plan` 澄清、深挖模式 | Matt `grill-me` / `grilling`；EGM `egm-brainstorm` |
| `0-plan` 规格、AC、纵向切片 | Matt `to-spec`、`to-tickets`；EGM `egm-draft` |
| `0-plan` 金鱼评审与批准 | EGM `egm-review`、`egm-resolve` |
| `0-build` 实施、TDD、排错 | Matt `implement`、`tdd`、`diagnosing-bugs`；EGM `egm-lite` |
| `0-build` 收尾代码评审 / `0-review` | Matt `code-review`；EGM `egm-lite` 对抗式 diff 评审 |
| 决策日志 | Matt `domain-modeling` ADR，简化为单文件追加 |
| `0-handoff` 阶段边界判断与交接 | Matt `handoff`、`ask-matt` 的 `PHASE-BOUNDARIES` |

</details>
