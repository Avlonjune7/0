---
name: me-tools
description: 应用个人工具偏好，适用于 CLI 或技能安装、Windows PATH 排障、需用 RTK 压缩超长命令输出、脚本静态检查（ShellCheck / PSScriptAnalyzer / actionlint）及 Go 交叉编译部署。普通项目日常命令不触发本技能。
---

# me-tools

## 工具选择

- 查文档优先已有专用 CLI 或 Context7；临时 Python 环境用 `uv` / `uvx`。
- 超长日志、测试或差异输出可按支持情况用 RTK 压缩（保留退出码与关键错误）；精确诊断或完整审查时读原始输出。
- 修改脚本且工具可用时定向检查：sh/bash 用 ShellCheck，PowerShell 用 PSScriptAnalyzer，GitHub Actions 用 actionlint。
- 缺少指定工具或技能时降级复用项目/官方能力并说明缺口；安装新工具或修改已安装技能须有明确授权，安装同名技能前先确认可否复用。反复执行的稳定步骤按需固化到脚本并记入项目 README。

## Windows 安装与 PATH

- 额外安装 CLI 与工具链优先 WinGet；支持自选目录时装到 `D:\code\cli\<工具名>`（固定路径遵循工具约定，项目依赖跟随项目）。
- 命令找不到时，核对当前进程与用户/系统 PATH 差异及已知入口（常用 `D:\code\cli`、WinGet 便携包 `D:\code\Portable\User`），仅按需补充当前进程 PATH 并核对解析到的实际可执行文件。

## Go 构建与部署

- 本机开发测试用宿主目标；部署 Debian 时先查明服务器架构再交叉编译 Linux 产物（含 CGO 时选兼容工具链）。目标平台变量仅在构建进程生效，部署后验证目标环境实际运行。
