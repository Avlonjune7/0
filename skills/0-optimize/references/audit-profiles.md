# 全站 4 象限 PSI 体检参考表

按项目实际技术栈启用对应象限；不适用项直接标 `N/A`，不强行凑指标。

| 象限 | 适用条件 | 核心指标 | 红 / 黄 / 绿参考阈值 | 常用采集命令 / 工具 |
| --- | --- | --- | --- | --- |
| **1. 入口与前端体验** | 有 Web UI、桌面端或 CLI 入口 | Web: LCP / INP / CLS、首包 JS 体积<br>CLI: 冷启动 / 高频命令耗时 | LCP: ≤2.5s 绿 / ≤4s 黄 / >4s 红<br>INP: ≤200ms 绿 / ≤500ms 黄<br>CLS: ≤0.1 绿 / ≤0.25 黄 | `npx lighthouse <url> --preset=desktop\|mobile`<br>公网 PSI API；构建产物 `dist/` 体积统计 |
| **2. 服务与数据链路<br>(RED + USE)** | 有后端服务、API、Worker 或数据库 | 接口 P50 / P95 延迟、错误率、吞吐；慢查询 / N+1 次数；CPU / 内存 / 锁热点 | 错误率 >0% 红；P95 视业务定基线；存在明确 N+1 或无索引全表扫为红 | `k6` / `oha` / `hey`；Go `go test -bench` + `pprof`；Python `py-spy` / `pytest`；Node `clinic`；DB `EXPLAIN ANALYZE` |
| **3. 工程与交付效率** | 所有工程通用 | 完整构建耗时、测试集耗时、产物 / 容器镜像体积 | 相对改前基线对比（无回归为绿，显著恶化为红） | `time` / `Measure-Command` 跑 build & test；镜像 `docker images` |
| **4. 架构与复杂度健康度** | 所有工程通用（`0-optimize` 核心） | 大文件（>500 行）、跨模块重复逻辑、死代码与无用依赖、循环依赖 / 冗余分层 | 大文件新增或核心链路跨多层空转标红；无新增且结构清晰标绿 | `scripts/baseline_snapshot.py`、`jscpd`、`knip`、`scc`、语言原生 linter |

## 采集硬规则

1. **Web 禁测 dev server**：必须基于 production build 采集，且同一场景至少跑 3 次取中位数。
2. **强制双场景对比**：Web 默认测「Desktop vs Mobile（CPU/网络节流）」；后端/CLI 默认测「常规负载 vs 压力/冷启动」。
3. **免动区保护**：已达标且非热路径的模块列入 `Passed`，后续批次严禁顺手重构。
