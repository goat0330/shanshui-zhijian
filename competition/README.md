# competition/ — IAIC 算法主线

本目录负责 IAIC 水域异常识别的完整评分链，与产品链硬隔离。

```text
DatasetAdapter
→ ModelClient
→ OutputParser
→ PostProcessor
→ Evaluation
→ SubmissionWriter
→ JSON Validator
```

唯一跨链接口为 `DetectionResult`。

## 数据开放前

优先完成：

1. 遥感 Pipeline 与 Mock 提交链；
2. 代理数据 Baseline；
3. JSON Schema 与校验；
4. 结构化实验记录。

产品链只通过 Mock DetectionResult 验证人工核验，不进入本目录。

## 数据开放后

立即切换为：

```text
官方数据审计
→ 官方 Adapter
→ 第一份合法 JSON
→ 第一轮评分
→ Bad Case
→ 优化与消融
```

## 约束

- 不依赖前端、数据库和工作流引擎；
- 官方数据不提交 Git；
- 所有格式、标签和指标在 8 月 1 日前均视为假设；
- 任何模型或框架由官方数据和运行环境决定；
- 代理数据指标不得写成赛事指标。
