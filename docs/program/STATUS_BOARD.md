# 山水智鉴 — 当前状态面板

> 核验日期：2026-07-29
> 事实优先级：运行时审计 → Git/CI → 本文件 → 历史报告

## Git 基线

| 项目 | 当前事实 |
|---|---|
| 正式 integration | `origin/integration/g0-g1-contract-freeze @ 2a5689d` |
| 当前检出分支 | `cycle3.1.1/ci-fix @ daff3b4`，Cycle 3.1.1 overlay 与控制面修复已提交 |
| 当前分支远程 | `origin/cycle3.1.1/ci-fix @ 0e08379`，本地包含未提交 overlay |
| develop | `origin/develop @ f950850` |
| main | `origin/main @ d00a94b` |

Cycle 3.1 的 A/B/C/D 模块已进入 integration；当前分支只处理 CI、可编辑
安装和仓库清理。它尚未自动成为新的正式 integration。

## 产品与工程状态

| 能力 | 状态 |
|---|---|
| RS-00 契约与比赛链 | 已集成 |
| ML-B1 Water Mask | 工程基线完成 |
| ML-B2 T1/T2 Water Change | 原型完成；真实数据可信评估待完成 |
| Candidate → Evidence → Review → Event → Replay | 已集成 |
| Workbench / Dashboard | Real-mode 骨架完成；用户产品验收待完成 |
| Python 测试收集 | 587 tests collected |
| Cycle 3.1.1 ML 回归 | 101 passed，3 warnings；需 Rasterio PROJ 环境变量 |
| RS-01B-3 持久化测试 | 21 passed + 4 XPASS，253.69s；主要耗时来自重复 GeoTIFF/全链路重跑，不是死锁 |
| Real Playwright | 24 passed，约 1.1 min；发现 MapLibre worker 与 CSS 非阻断 warning |
| 全量 Python Gate | 未完成：`pytest -q` 超过 5 分钟，需按测试域拆分定位 |
| Cycle 3.1.1 overlay | 已覆盖并保留仓库外备份；远端 CI 尚未重跑 |
| OpenChamber | 已停机，正在进行单运行时与 Actor/Session Epoch 迁移 |

## 当前 P0

1. 先清理并拆分全量测试超时，再验证并合回 `cycle3.1.1/ci-fix`。
2. 清理重复生成脚本、缓存和失效文档链接。
3. 用真实重庆 T1/T2 数据完成 ML-B2 指标。
4. 完成 Workbench / Dashboard 用户验收。
5. OpenChamber 只保留一套活动数据源和插件运行时。

## 本机验证前置条件

PostgreSQL/PostGIS 注入的 `PROJ_LIB` 和 `GDAL_DATA` 会覆盖 Rasterio
自带 PROJ 数据库，导致 EPSG 创建失败。运行栅格测试前使用当前 Python
环境对应的 Rasterio 数据目录，或在 CI 中保持干净的 GIS 环境：

```powershell
$env:PROJ_LIB = "D:\py\Python3\Lib\site-packages\rasterio\proj_data"
$env:GDAL_DATA = "D:\py\Python3\Lib\site-packages\rasterio\gdal_data"
```

这只是本机环境修正，不代表生产代码需要硬编码路径。

## 控制面规则

- Agent A/B/C/D/E 是稳定 Actor，Session 是可轮换 Epoch。
- 禁止直接编辑 `ensemble.db` 的 `lead_session_id` 或
  `reported_to_lead`。
- Cycle 开始前必须先提交并冻结完整的
  `.opencode/ensemble-efficiency.json`。
- Agent 工作完成后立即运行增量 Gate，不事后集中补跑。
- 运行时状态与本文件冲突时，以 `agent-control-plane` 审计为准并修订本文件。
