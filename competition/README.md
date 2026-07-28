# competition/ — IAIC 比赛评测链

本目录只负责比赛输入、推理、预测记录、评测和提交，不依赖产品前端、人工审核、事件聚合、工单或治理状态。

```text
CompetitionInputAdapter
→ InferenceTask
→ ModelProvider / Pipeline
→ PredictionRecord
→ SubmissionBundle
→ SchemaValidator
→ SubmissionAttempt
```

## 1. 与产品链的边界

比赛链可以共享：

- 原始资产与数据 Manifest；
- 预处理、切片、推理和模型权重；
- 模型运行记录、配置和版本；
- 通用几何、栅格和时间工具。

比赛链不得读取或依赖：

- `AnomalyEvent`；
- `ReviewDecision`；
- `AlertDelivery`；
- `IncidentCase` 或 WorkOrder；
- 前端页面中的人工确认状态；
- 产品链对候选的合并、拆分和重编号。

`DetectionResult` 仅作为 V0 兼容输出。正式比赛链使用 `PredictionRecord`，正式产品链使用 `Observation / DetectionCandidate`。

## 2. 数据开放前

必须完成：

1. 代理数据和 Mock 输入 Adapter；
2. 样本 ID、顺序和空结果规则；
3. PredictionRecord Schema；
4. SubmissionBundle 与 JSON Validator；
5. golden test；
6. 遥感验证集与 Baseline Report；
7. 配置、数据和代码版本可复现。

## 3. 数据开放后 24 小时

```text
0—4h   数据审计、许可证和目录确认
4—8h   CompetitionInputAdapter
8—12h  最小合法推理
12—18h 第一份 SubmissionBundle
18—24h 首次提交、错误分层与 Baseline Report V1
```

禁止在首日进行大模型替换、复杂融合或平台重构。

## 4. 遥感 V0

当前重庆遥感 Spike 位于：

```text
competition/spikes/chongqing_rs_demo/
```

它用于验证数据处理、空间配准、变化候选、产品输出和评测接口，不代表官方赛题形式和指标。

下一阶段见：

- `docs/01_赛题与实验.md`
- `docs/07_实施管理/01_遥感能力提升路线图.md`

## 5. 约束

- 官方数据、权重、数据库和大体积结果不提交 Git；
- 代理数据指标不得写成赛事指标；
- 所有输出必须带数据版本、代码版本、配置哈希和模型版本；
- 同一输入和配置应得到稳定的样本 ID 与输出顺序；
- 空预测、无数据和推理失败必须是不同语义；
- 官方 Schema 变化只修改 Adapter、Exporter 和 Validator。
