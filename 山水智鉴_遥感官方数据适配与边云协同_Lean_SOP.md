# 山水智鉴｜遥感官方数据适配与边云协同 Lean SOP

> 适用范围：官方数据开放前后的遥感任务适配、当前重庆 4 km × 4 km 代理场景优化、高点视频边缘感知、云端多源融合与比赛提交。  
> 方法：Lean Project Method。只冻结目标、边界、交付和验收，不提前限定具体模型、代码行号、函数拆法或技术栈。

---

## 1. SOP 目标

确保当前代理数据上的研发不会绑定某一种文件格式、任务类型或模型，使官方数据开放后能够快速完成：

```text
官方数据审计
→ 数据与任务适配
→ 最小合法推理
→ PredictionRecord
→ SubmissionBundle
→ 首次提交
```

同时保持产品链和比赛链独立：

```text
产品治理链：
Asset → Observation → Candidate → Event → Review

比赛评测链：
CompetitionInput → InferenceTask → PredictionRecord → SubmissionBundle
```

---

## 2. 角色分工

### 用户｜需求提出者、架构统筹者、最终验收人

负责：

- 决定本轮目标、范围和优先级；
- 决定是否接受架构变化；
- 判断交付是否满足比赛和产品目标；
- 冻结或调整关键决策。

### 助手｜需求澄清、轻量规划、一致性检查

负责：

- 先读取当前仓库状态和既有决策；
- 只提出影响范围、架构或验收的关键问题；
- 将任务整理为轻量工作包；
- 检查比赛链、产品链和边云边界是否冲突；
- 检查文档、代码和项目驾驶舱是否一致。

### 执行 Agent｜具体实现与验证

负责：

- 自主选择合理实现方式；
- 完成代码、测试、报告和必要文档；
- 不越过冻结边界；
- 留下可复现的交接记录。

### 架构师 Partner｜跨模块设计审查

只在以下情况介入：

- 新增或改变核心领域对象；
- 改变产品链与比赛链边界；
- 改变边缘端与云端职责；
- 引入新的基础设施或重大技术依赖；
- 一项修改同时影响视频、遥感和事件融合。

---

## 3. 冻结原则

任何工作包都必须遵守以下原则：

1. **官方数据格式未知，不把 Pipeline 写死在 GeoTIFF、目录命名或多时相输入上。**
2. **文件格式变化由 Adapter 承接；任务语义变化由 TaskSpec、TaskRouter 和 PerceptionTool 承接。**
3. **产品治理链和比赛评测链硬隔离。**
4. **人工 Review、Event 合并和工单状态不得改变比赛 PredictionRecord。**
5. **光学与 SAR 共享资产契约，但使用独立 ARD 和质量规则。**
6. **当前 Sentinel-1 多时相方法是可插拔工具，不是整个遥感系统。**
7. **高点视频主要在边缘端完成实时初筛；复杂推理、遥感和多源事件融合主要在云端。**
8. **视频与遥感先在 Candidate/Event 层晚融合，不提前做原始特征级强融合。**
9. **当前 4 km × 4 km 场景用于验证框架和算法，不代表正式赛题精度。**
10. **目标架构不等于当前已实现能力。**

---

## 4. 每轮工作流程

## Step 0｜检查当前状态

执行 Agent 开始前必须阅读与当前任务直接相关的内容：

- `README.md`
- `山水智鉴_项目驾驶舱.md`
- `docs/00_项目总纲.md`
- `docs/01_赛题与实验.md`
- `docs/06_架构设计/`
- `docs/07_实施管理/`
- 当前分支、相关代码、测试和未合并 PR

输出一段状态摘要：

```text
当前已有：
当前缺口：
本轮只解决：
本轮明确不解决：
依赖与风险：
```

不得仅根据旧聊天记录判断仓库状态。

---

## Step 1｜定义单一工作包

每轮只选择一个主要工作包：

### A｜官方数据适配

解决：

- 官方文件和目录如何进入系统；
- 样本 ID、顺序、资产角色和任务类型如何表达；
- 官方输出如何导出和校验。

### B｜遥感算法提升

解决：

- 当前 Sentinel-1/Sentinel-2 算法质量；
- 多时相、质量门禁、对象级后处理和候选排序；
- 不改变比赛与产品边界。

### C｜高点视频边缘链

解决：

- 视频接入、解码、质量、ROI、轻量识别、时序聚合；
- Candidate、Evidence 和断网缓存。

### D｜云端事件融合

解决：

- 视频 Candidate 与遥感 Candidate 的时空关联；
- Event 聚合、冲突证据和人工研判；
- 不修改比赛输出。

禁止在同一工作包中同时进行：

- 数据库大迁移；
- 前端重写；
- 新模型替换；
- 领域对象重构；
- 多模态融合；
- 官方提交格式改造。

---

## Step 2｜形成最小任务说明

普通任务只需在 Issue 或任务说明中写清：

```text
目标：
输入：
输出：
边界：
验收：
依赖：
```

只有在必要时创建独立文档：

| 文档 | 何时使用 |
|---|---|
| `BRIEF.md` | 目标、范围或关键需求不清楚 |
| `DESIGN.md` | 涉及接口、领域对象或跨模块边界 |
| `PLAN.md` | 工作需拆成多个可验收阶段 |
| `ACCEPTANCE.md` | 验收复杂或需要多角色确认 |
| `STATUS.md` | 长周期、多成员并行任务 |
| `RUNBOOK.md` | 需要稳定重复运行或故障恢复 |

不要默认创建全部文档。

---

## Step 3｜先冻结契约，再决定实现

涉及遥感或官方数据适配时，先明确：

```text
AssetRef
InferenceTask
TaskSpec
PredictionRecord
Observation
DetectionCandidate
Evidence
```

至少回答：

1. 输入资产是什么；
2. 是否带 CRS、时间和空间信息；
3. 样本是整景、切片、T1/T2 配对还是多资产；
4. 任务是分类、检测、分割、变化检测还是异常评分；
5. 输出是像素、框、掩膜、图斑还是类别；
6. 无数据、无变化和推理失败如何区分；
7. 产品对象与比赛对象分别是什么。

契约确定后，执行 Agent 自主选择内部代码结构和实现方式。

---

## Step 4｜实施最小纵切

每个工作包优先完成一条最小可运行纵切。

### 官方数据适配最小纵切

```text
Fixture
→ CompetitionInputAdapter
→ InferenceTask
→ Mock/现有工具
→ PredictionRecord
→ SubmissionBundle
→ Validator
```

至少准备四类 Fixture：

- 整景 GeoTIFF；
- PNG/JPEG 切片；
- T1/T2 配对；
- S1＋S2 多资产样本。

### 当前遥感最小纵切

```text
Asset
→ SAR ARD
→ SarTemporalChangeTool
→ Observation
→ DetectionCandidate
→ Evidence
```

多时相算法应允许在官方只提供 T1/T2 时退化为配对变化模式。

### 视频边缘最小纵切

```text
授权 MP4
→ 解码与时间轴
→ 质量检查
→ 水面 ROI
→ 轻量识别或 Mock
→ 时序聚合
→ Candidate
→ 关键帧 Evidence
```

### 事件融合最小纵切

```text
Mock VideoCandidate
+
RemoteSensingCandidate
→ 时空匹配
→ AnomalyEvent
→ Review
```

---

## Step 5｜验证

每轮至少验证四类内容：

### 1. 契约验证

- 字段和单位明确；
- ID 稳定；
- 空结果合法；
- 不同任务类型不会混用字段；
- Schema 变化有兼容说明。

### 2. 可复现验证

保存：

```text
run_id
data_version
task_spec
config
code_commit
model_version
environment
output_manifest
```

同一输入、配置和版本应得到稳定输出。

### 3. 边界验证

必须证明：

- 产品 Review 不改变比赛 PredictionRecord；
- Event 合并不改变 SubmissionBundle；
- S2 缺失不会被解释为无异常；
- 视频边缘端只生成 Observation/Candidate，不直接生成治理结论；
- 遥感 Pipeline 不依赖前端页面和工单状态。

### 4. 失败验证

至少覆盖：

- 缺文件；
- 无 CRS；
- 资产角色缺失；
- 无有效像元；
- 空预测；
- 模型失败；
- 重复导入；
- 网络或边缘补传中断。

---

## Step 6｜交付和交接

执行 Agent 完成后必须提交：

```text
本轮目标：
实际修改文件：
新增或改变的契约：
运行与测试结果：
生成的产物：
已知限制：
未完成项：
下一建议工作包：
不可宣称内容：
```

同时更新：

- GitHub Issue；
- PR；
- 必要的设计或验收文档；
- `山水智鉴_项目驾驶舱.md` 中的状态和下一 Gate。

README 只更新稳定能力，不记录每日进度。

---

## 5. 当前工作包顺序

## P0-1｜RS-00 官方数据自适应框架

目标：

> 使用当前重庆代理数据模拟多种官方数据组织形式，证明系统不会绑定某一种文件和任务格式。

最小交付：

- `AssetRef`
- `InferenceTask`
- `TaskSpec`
- `PredictionRecord` 类型联合
- `CompetitionInputAdapter`
- `CompetitionExporter`
- 四类 Fixture
- 契约和 golden test

验收：

- 核心算法不扫描目录猜测任务；
- 样本 ID 和顺序稳定；
- 整景、切片、配对和多资产都能进入统一任务层；
- 产品 Review 不影响 SubmissionBundle。

---

## P0-2｜RS-01 Sentinel-1 工具化与提升

目标：

> 将当前 S1 方法封装为可替换的 `SarTemporalChangeTool`，并提升当前 4 km × 4 km 场景的稳定性。

允许改进：

- 同轨资产筛选；
- 多时相 median/MAD；
- 当前多景合成；
- 持续性门禁；
- DEM、layover/shadow 和数据质量；
- 对象级图斑和候选排序；
- S2 晴空证据。

验收：

- 工具通过 TaskRouter 调用；
- 不依赖固定目录和文件名；
- 可接受多时相输入，也可退化为 T1/T2；
- 输出 Observation、Candidate 和 Evidence；
- 不直接产生 Event、告警或比赛提交 JSON。

---

## P1｜VIDEO-00 高点视频边缘最小纵切

目标：

> 用一段授权视频验证边缘侧实时初筛和证据生成。

验收：

- 解码、时间戳、质量和 ROI 可追溯；
- 单帧噪声不会直接成为 Event；
- 输出 Candidate 和关键帧/短片段 Evidence；
- 网络中断时可以本地缓存和幂等补传；
- 云端可以读取同一 Candidate 契约。

---

## P1｜FUSION-00 事件级晚融合

目标：

> 使用 Mock 视频 Candidate 和真实遥感 Candidate 验证云端时空融合。

验收：

- 融合依据明确；
- 缺失模态可运行；
- 冲突证据被保留；
- 只生成“疑似/待研判”Event；
- 不自动声称非法采砂、四乱或污染；
- 不修改比赛 PredictionRecord。

---

## 6. 官方数据开放后的应急 SOP

## 0—4 小时｜数据审计

只确认：

- 文件和目录；
- 许可证；
- 模态；
- CRS、分辨率和时间；
- 标签；
- 样本 ID 和顺序；
- 官方任务；
- 指标；
- 输出 Schema；
- 推理环境与网络限制。

输出一份简短 `DATA_AUDIT.md`。

## 4—8 小时｜Adapter 与 TaskSpec

完成：

```text
官方样本
→ CompetitionInputAdapter
→ InferenceTask
```

先让一条样本合法进入系统，不优化模型。

## 8—12 小时｜最小推理

选择最接近任务的现有 PerceptionTool 或 Mock Baseline，完成：

```text
InferenceTask
→ PredictionRecord
```

## 12—24 小时｜首个提交闭环

完成：

```text
PredictionRecord
→ CompetitionExporter
→ SubmissionBundle
→ Validator
→ 首次提交
```

首日禁止：

- 大规模重写架构；
- 重做前端；
- 同时更换多个模型；
- 建复杂特征融合；
- 以人工 Review 修正比赛结果。

---

## 7. Gate

### Gate F0｜数据和任务可适配

- 四类 Fixture 通过；
- Asset、Task、Prediction 契约冻结；
- 样本 ID、顺序和空结果稳定。

### Gate F1｜遥感工具可替换

- 当前 S1 Pipeline 成为 PerceptionTool；
- 多时相和 T1/T2 两种输入均可运行；
- Observation/Candidate 与 PredictionRecord 分离。

### Gate F2｜当前场景稳定提升

- 同轨和质量控制生效；
- 多时相与持续性可配置；
- 候选碎片和明显瞬时噪声减少；
- Run 可复现；
- 不把当前结果称为正式赛事精度。

### Gate F3｜视频边缘闭环

- MP4/视频源到 Candidate；
- Evidence 和时间轴正确；
- 断网缓存和幂等补传可验证。

### Gate F4｜多源事件融合

- 视频和遥感只在 Candidate/Event 层融合；
- 支持缺失和冲突模态；
- Event 可追溯且需要人工研判。

### Gate F5｜官方数据 24 小时切换

- 官方 Adapter；
- 最小推理；
- PredictionRecord；
- SubmissionBundle；
- Validator；
- 首次提交记录。

---

## 8. 停止规则

出现以下情况时停止继续实现，回到设计或需求确认：

- 官方任务语义不明确；
- 一个对象同时承担产品和比赛含义；
- Agent 需要通过猜测文件名判断任务；
- 光学和 SAR 被强行使用同一预处理逻辑；
- 边缘端准备直接创建治理结论；
- 视频和遥感准备在无对齐数据时做特征级融合；
- 为了一个 Spike 引入大规模基础设施；
- 修改范围同时跨越三个以上核心模块；
- 没有明确验收标准；
- 仓库文档与当前代码状态冲突。

---

## 9. 标准启动指令

可直接交给执行 Agent：

```text
使用《山水智鉴｜遥感官方数据适配与边云协同 Lean SOP》推进本任务。

先读取当前仓库状态、项目驾驶舱、相关架构文档和代码，只总结与本任务直接有关的已有能力、缺口和约束。

本轮工作包：
[填写 RS-00 / RS-01 / VIDEO-00 / FUSION-00 或单一自定义任务]

目标：
[填写结果]

边界：
- 不改变产品链与比赛链的隔离；
- 不预设官方最终数据格式和任务类型；
- 不进行与本轮无关的前端、数据库或基础设施重构；
- 实现方式和技术细节由执行 Agent 自主决定。

开始前给出简短的目标、输入、输出、风险和验收；只有影响架构、范围或验收的问题才提问。
完成后提交修改文件、测试结果、已知限制、下一工作包和不可宣称内容。
```
