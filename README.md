# 山水智鉴

> 面向水域异常感知、证据核验与治理系统集成的开放中间件。  
> 一个主项目、一套共享数据与模型资产、两条独立业务链、两个竞赛版本。

## 1. 项目定位

山水智鉴接入高点视频、遥感影像、赛事指定模型、自研模型及第三方算法，将模型观测组织为可追溯候选和证据，并支持人工研判、外部治理系统集成与算法评测。

项目不重复建设摄像头硬件、无人机平台、完整河长制平台或单一“万能模型”。

### 产品治理链

```text
Source
→ Asset
→ Observation
→ DetectionCandidate
→ AnomalyEvent
→ ReviewDecision
→ AlertDelivery
→ IncidentCase / 外部治理系统
```

### 比赛评测链

```text
CompetitionInput
→ InferenceTask
→ PredictionRecord
→ SubmissionBundle
→ SubmissionAttempt
```

两条链可以共享输入资产、模型运行、预处理代码、权重、数据版本和运行日志，但产品事件不得反向改变比赛预测记录。

## 2. 当前状态

`origin/integration/g0-g1-contract-freeze` 已完成 Cycle 3.1 的模块集成；
当前检出分支 `cycle3.1.1/ci-fix` 已应用 Cycle 3.1.1 CI/ML readiness
overlay（本地尚未提交），仍未合入 `develop`：

```text
GEE 数据
→ Sentinel-1 双时相 SAR 水体变化检测
→ 变化候选图斑
→ Observation / DetectionCandidate
→ Evidence / 人工 Review
→ Event Version
→ Replay
→ SQLite 持久化
→ React Workbench / Dashboard
```

当前已经验证的是“数据能够进入系统并形成可核验候选”，尚未验证的是正式赛题精度、高点视频闭环和生产级可靠性。

| 能力 | 状态 |
|---|---|
| GEE 多源数据下载 | 已完成 |
| Sentinel-1 双时相变化 Pipeline | 已完成 V0 |
| CRS、地理重投影、三态语义 | 已完成 |
| FastAPI + SQLite + 演示页面 | 已完成 V0 |
| 人工验证集与量化精度 | 待完成 |
| 真实 COG → TiTiler → MapLibre | 待修复 |
| Competition Adapter / SubmissionBundle | 已进入 integration |
| Observation → Candidate → Review → Event | 已进入 integration |
| React + MapLibre 研判工作台 | Real-mode 骨架已进入 integration，待用户产品验收 |
| ML-B2 T1/T2 水体变化原型 | 已进入 integration，真实数据可信评估待完成 |
| Cycle 3.1.1 ML 回归 | 101 passed；全量 587 tests 尚需按域拆分验证 |
| OpenChamber 多 Agent 控制面 | 正在迁移为 Actor / Session Epoch；禁止手改数据库 |
| 高点视频最小纵切 | 待实现 |
| PostgreSQL/PostGIS、权限、Outbox | 产品化阶段 |

当前实测状态见 [`docs/program/STATUS_BOARD.md`](docs/program/STATUS_BOARD.md)，
OpenChamber 迁移边界见
[`docs/program/GEOCODE_TO_OPENCHAMBER_MIGRATION_SOP.md`](docs/program/GEOCODE_TO_OPENCHAMBER_MIGRATION_SOP.md)。

## 3. 当前唯一 P0

1. 拆分并定位全量测试超时，再将 `cycle3.1.1/ci-fix` 验证并合回 integration；
2. 用真实重庆 T1/T2 数据完成 ML-B2 可复现指标；
3. 完成 Workbench / Dashboard 用户产品验收；
4. 将 OpenChamber 收敛到单一运行时并启用 Actor / Session Epoch；
5. 修复真实 COG、TiTiler TileJSON 与 MapLibre 图层链。

## 4. 仓库结构

```text
shanshui-zhijian/
├── competition/                  # 比赛评测链
│   └── spikes/chongqing_rs_demo/ # 重庆遥感 V0
├── core/
│   └── schemas/                  # 当前 Schema 与后续领域契约
├── apps/workbench_api/           # 正式 React API 入口
├── services/                     # Repository、TiTiler 与 Legacy/兼容服务
├── ml/                           # 训练、评估、推理与水体变化
├── data/                         # 目录与样例说明；原始数据和数据库不提交
├── docs/
│   ├── 00_项目总纲.md
│   ├── 01_赛题与实验.md
│   ├── 02_产品与业务方案.md
│   ├── 03_技术架构与开源底座.md
│   ├── 04_证据与风险台账.md
│   ├── 05_竞赛交付/
│   ├── 06_架构设计/              # 架构师设计原文与索引
│   └── 07_实施管理/              # 迁移、遥感路线、Issue 与协作规范
├── references/                   # 市场、采购与开源审计
├── tests/
├── 山水智鉴_项目驾驶舱.md
└── CONTRIBUTING.md
```

## 5. 架构文档入口

- [`docs/06_架构设计/01_总体分层架构.md`](docs/06_架构设计/01_总体分层架构.md)
- [`docs/06_架构设计/02_领域模型与接口契约.md`](docs/06_架构设计/02_领域模型与接口契约.md)
- [`docs/06_架构设计/03_前后端工程框架.md`](docs/06_架构设计/03_前后端工程框架.md)
- [`docs/06_架构设计/04_高点视频感知框架.md`](docs/06_架构设计/04_高点视频感知框架.md)
- [`docs/06_架构设计/05_边云协同与数据流.md`](docs/06_架构设计/05_边云协同与数据流.md)
- [`docs/07_实施管理/01_遥感能力提升路线图.md`](docs/07_实施管理/01_遥感能力提升路线图.md)

## 6. 两个比赛

| 比赛 | 项目作用 | 主要验收 |
|---|---|---|
| IAIC 行业智能体创新挑战赛 | 验证指定任务下的识别、适配、提交和消融 | 官方数据、合法提交、平台评分、Bad Case、代码 |
| 中国研究生智慧城市大赛 | 将已验证算法扩展为完整产品与治理价值 | 产品方案、业务闭环、原型、实施和商业材料 |

比赛链不依赖产品前端、人工审核结果和工单状态。产品链可以使用比赛模型，但必须通过适配器生成独立的 Observation 和 Candidate。

## 7. 事实边界

可以宣称：

- 已跑通重庆两江 Sentinel-1 双时相变化检测 V0；
- 已形成可进入人工核验的真实变化候选；
- 已完成 SQLite 持久化和演示 E2E；
- 已形成八层目标架构及双链领域模型。

不能宣称：

- 507 条候选等于 507 个真实异常；
- 当前结果已经达到正式赛题精度；
- 已完成高点视频识别；
- 已形成生产级治理平台；
- 已完成真实 COG 瓦片服务闭环。

## 8. 当前 Gate

### Gate F0｜契约冻结

- 双链边界写入顶层文档；
- 最小领域对象字段确定；
- 生命周期、质量和错误状态分离；
- Mock Schema 具备契约测试。

### Gate F1｜遥感可验证

- 人工验证集可重复加载；
- 指标脚本输出固定报告；
- 真实 COG 由 TiTiler 加载；
- 同一配置重复运行结果一致。

### Gate F2｜评测链可提交

- 官方或 Mock 输入不丢样本；
- PredictionRecord 顺序与 ID 稳定；
- 空结果可表达；
- SubmissionBundle 通过 Schema 和 golden test。

完整 Gate 见 [`docs/07_实施管理/00_架构迁移计划.md`](docs/07_实施管理/00_架构迁移计划.md)。

## 9. 治理框架

山水智鉴采用**五 Agent 治理框架**，详见：

| 文档 | 说明 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | 多 Agent 治理框架总纲 |
| [`agents/`](agents/) | 五 Agent 角色定义 + 交接模板 |
| [`docs/program/STATUS_BOARD.md`](docs/program/STATUS_BOARD.md) | Agent 状态面板 |
| [`docs/program/DECISION_LOG.md`](docs/program/DECISION_LOG.md) | 决策日志 |
| [`docs/program/CONTRACT_GAP_REGISTER.md`](docs/program/CONTRACT_GAP_REGISTER.md) | 合同缺口登记 |
| [`docs/07_实施管理/02_Git分支与交付规范.md`](docs/07_实施管理/02_Git分支与交付规范.md) | 分支与交付规范 |
| [`.github/agent-owners.yml`](.github/agent-owners.yml) | 代码所有权映射 |
| [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) | PR 模板 |
| [`.github/ISSUE_TEMPLATE/agent-task.yml`](.github/ISSUE_TEMPLATE/agent-task.yml) | Agent 任务 Issue 模板 |
