# 山水智鉴

> 一个主项目、一套共享代码资产、两个竞赛版本、两套验收口径。

## 项目定位

山水智鉴面向高点视频、遥感影像、赛事指定模型、自研模型及第三方算法，提供统一的异常结果接入、证据编排、人工核验和反馈评测能力。

```text
任意模型
→ ModelAdapter
→ DetectionResult
→ EvidenceBundle
→ AnomalyAlert
→ 人工核验
→ GovernanceEvent / 外部业务系统
→ Replay / Eval
```

项目不重复建设无人机硬件平台、完整河长制平台或单一识别模型。当前产品形态为：

```text
开放治理事件中间件
＋
异常证据核验工作台
＋
面向既有平台的 API 集成能力
```

## 两个比赛

| 比赛 | 项目作用 | 主要验收 |
|---|---|---|
| IAIC 行业智能体创新挑战赛 | 验证水域异常识别与指定基座模型适配 | 官方数据、推理 JSON、平台评分、消融和代码 |
| 中国研究生智慧城市大赛 | 将算法扩展为完整水域治理产品 | 产品方案、原型、业务闭环、商业模式和答辩 |

## 当前阶段

**市场与源码审计已经完成，进入技术决策冻结与实现前 Spike。**

当前不再继续横向寻找完整平台，优先验证三件事：

1. 遥感 Pipeline 与 Mock 提交链；
2. COG + TiTiler 遥感成果服务；
3. DetectionResult → EvidenceBundle → AnomalyAlert → 人工核验。

## 六项里程碑

| 里程碑 | 状态 |
|---|---|
| 项目定位与双赛关系 | 已完成 |
| 市场与采购调研 | 已完成 |
| 开源仓库静态与文件级审计 | 已完成 |
| 实现前技术 Spike | 待启动 |
| 代理 Baseline 与 Mock 提交链 | 待启动 |
| 官方数据接入与首次提交 | 等待 2026-08-01 |

## 仓库结构

```text
8.1开始_山水智鉴比赛/
├── README.md
├── 山水智鉴_项目驾驶舱.md
├── pyproject.toml
├── docs/
│   ├── 00_项目总纲.md
│   ├── 01_赛题与实验.md
│   ├── 02_产品与业务方案.md
│   ├── 03_技术架构与开源底座.md
│   ├── 04_证据与风险台账.md
│   └── 05_竞赛交付/
├── competition/
├── data/
└── references/
```

## 文档职责

| 文件 | 职责 |
|---|---|
| `山水智鉴_项目驾驶舱.md` | 项目负责人维护状态、决策、风险和下一 Gate |
| `docs/00_项目总纲.md` | 项目唯一顶层事实源 |
| `docs/01_赛题与实验.md` | 赛题、数据、Baseline、评测和消融 |
| `docs/02_产品与业务方案.md` | 产品能力、用户、对象、人机边界和 MVP |
| `docs/03_技术架构与开源底座.md` | 架构、技术栈、源码参考和依赖边界 |
| `docs/04_证据与风险台账.md` | 市场证据、产品假设、可宣称和禁止宣称 |
| `references/` | 十个市场项目及五个开源项目的详细审计 |

## 协同开发

> **GitHub**: https://github.com/goat0330/shanshui-zhijian

### 分支策略（Git Flow 简化版）

```
main（受保护）—— 只接受 develop PR，需 1 人 Review
└── develop ──── 日常集成分支
    ├── feature/rs-pipeline       # 遥感检测管线
    ├── feature/backend-services   # FastAPI + TiTiler
    ├── feature/frontend           # 前端模板
    ├── feature/core-schemas       # Pydantic 数据模型
    ├── feature/iaic-integration   # IAIC 算法赛适配
    ├── feature/smart-city         # 智慧城市产品赛方案
    └── feature/tests              # 测试
```

### 基本协作流程

```text
1. 开发前：git checkout develop → git pull
2. 切到自己的 feature 分支开发
3. 完成后：git add . → git commit -m "说明" → git push
4. 在 GitHub 上提 Pull Request → develop（轻量审核）
5. develop 稳定后 PR → main（需另一个人 Review + Approve）
```

| 命令 | 含义 |
|------|------|
| `git pull` | 把远程最新代码拉到本地 |
| `git add .` | 暂存所有改动 |
| `git commit -m "xxx"` | 提交到本地 |
| `git push` | 推送到 GitHub |

## 当前 Gate

官方数据开放前必须完成：

- 技术栈 V1 冻结；
- Mock 数据到 JSON 校验链可运行；
- 遥感 Pipeline 骨架可运行；
- COG + TiTiler Spike 可运行；
- 人工核验最小链可运行；
- 四份竞赛工作稿形成 V0。
