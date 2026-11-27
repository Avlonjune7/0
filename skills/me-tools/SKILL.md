---
name: me-tools
description: 应用个人工具偏好，适用于 CLI 或技能安装、Windows PATH 与脚本执行排障、脚本静态检查（ShellCheck / PSScriptAnalyzer / actionlint）、Go 交叉编译部署及 Android 便携构建。普通项目日常命令不触发本技能。
---

# me-tools

## 工具选择

- 查文档优先已有专用 CLI 或 Context7；独立 `.py` 脚本直接用 `python`（旧进程 PATH 未刷新时回退 `uv run python`），临时 Python 环境用 `uv` / `uvx`。
- 修改脚本且工具可用时定向检查：sh/bash 用 ShellCheck，PowerShell 用 PSScriptAnalyzer，GitHub Actions 用 actionlint。
- 缺少指定工具或技能时降级复用项目/官方能力并说明缺口；安装新工具或修改已安装技能须有明确授权，安装同名技能前先确认可否复用。反复执行的稳定步骤按需固化到脚本并记入项目 README。

## Windows 安装与 PATH

- 额外安装 CLI 与工具链优先 WinGet；支持自选目录时装到 `D:\code\cli\<工具名>`（固定路径遵循工具约定，项目依赖跟随项目）。
- 命令找不到时，核对当前进程与用户/系统 PATH 差异及已知入口（常用 `D:\code\cli`、WinGet 便携包 `D:\code\Portable\User`），仅按需补充当前进程 PATH 并核对解析到的实际可执行文件。
- PowerShell 禁止执行 `.ps1` 时改用 `.cmd` 或 `cmd /c` 调用（如 `cmd /c "npx -y pnpm ..."`）；解压深层目录压缩包避开 `MAX_PATH` 限制时，优先短根目录 + `tar.exe -xf` 而非 `Expand-Archive`。
- 打包用于云平台或 Linux 上传的 `.zip` 时，避免使用 PowerShell `Compress-Archive`（会写入 `\` 反斜杠路径，易触发 EdgeOne Pages 等平台非法字符报错）；改用 `tar.exe -a -cf <out.zip> -C <dir> .` 或 Python `zipfile` 显式写入 `/` 路径分隔符，并确认入口文件位于压缩包根目录。

## Go 构建与部署

- 本机开发测试用宿主目标；部署 Debian 时先查明服务器架构再交叉编译 Linux 产物（含 CGO 时选兼容工具链）。目标平台变量仅在构建进程生效，部署后验证目标环境实际运行。
- 个人生产服务器默认为 Debian 12/13（`linux-amd64`），采用 `systemd` 托管服务、宝塔仅做 Nginx 反代与 SSL；编写部署/运维指令时优先给出可直接整段复制执行的命令块（不留中文占位符，用 `ls -t ... | head -n1` 选最新产物）。
- `systemd` 启用 `DynamicUser=yes` + `StateDirectory` 时，以 `root` 离线恢复或替换数据目录文件后，须执行 `chown -R --reference=<目录>/ <目录>/` 还原动态用户属主再启动服务，避免无权打开数据库。
- 用户说“更新”或服务已在运行时，只给现有实例升级步骤（上传校验、备份、替换、重启、验证与回滚），不重复首次装机流程。

## Android 便携构建

- 无 Android Studio 时，将便携 JDK 与 `cmdline-tools` 解压到短根目录（用完即删），仅安装目标 `platforms`/`build-tools`；国内网络下用临时 `--init-script` 的 `beforeSettings` 原地将 `google()`/`mavenCentral()` 重写为阿里云镜像（不用 `settingsEvaluated` 追加），构建加 `--no-daemon`。
