# GitHub Issues 清单

以下 Issue 可直接拆给成员或 Agent。

## P0

### ARC-01｜冻结最小领域 Schema

交付：

- Asset；
- Observation；
- DetectionCandidate；
- PredictionRecord；
- Evidence；
- JSON 示例；
- 契约测试。

验收：字段含义、ID、时间、空间、质量和版本明确。

### ARC-02｜DetectionResult 兼容映射

交付：

- ProductCompatibilityAdapter；
- CompetitionCompatibilityAdapter；
- golden fixtures。

验收：旧结果可稳定映射到两条链，Review 不影响 Prediction。

### RS-01｜建立重庆遥感验证集

交付：

- validation.gpkg；
- 标注指南；
- 20—50 样区；
- 样区切片。

验收：两名成员可以按指南复现同一标签语义。

### RS-02｜遥感指标与 Bad Case

交付：

- 水体和变化评测脚本；
- metrics.json；
- slice_metrics.json；
- Bad Case 图册。

验收：固定 Run 可重复生成同一报告。

### RS-03｜修复 COG + TiTiler 真瓦片链

交付：

- COG 验证；
- TileJSON；
- MapLibre raster source；
- 自动测试。

验收：移除静态 PNG 后仍能浏览原图和结果。

### COMP-01｜Mock Competition Adapter

交付：

- 输入样例；
- Adapter；
- InferenceTask；
- 样本 ID 和顺序测试。

### COMP-02｜PredictionRecord 与 SubmissionBundle

交付：

- Schema；
- Exporter；
- Validator；
- golden test；
- 空结果测试。

### GOV-01｜同步 develop 到 main

交付：

- PR；
- 状态说明；
- README；
- 标签；
- 启动命令验证。

## P1

### RS-04｜S1 质量门禁

轨道、入射角、坡度、layover/shadow、斑点滤波 A/B。

### RS-05｜多时相稳健变化

历史合成、IQR/MAD、持续性和季节变化抑制。

### RS-06｜对象级候选排序

面积、形状、稳定水体、岸线、坡度、Top-N。

### PROD-01｜Observation/Candidate 双写

保持旧 API 可用，新增正式对象和追溯关系。

### VIDEO-01｜单视频最小纵切

授权 MP4 → ROI → Candidate → Evidence → Review。

## P2

### DATA-01｜PostGIS 迁移评估

先测空间查询、并发和数据量，再决定迁移。

### WEB-01｜React 五页壳

只建立 API 边界和路由，不阻塞当前演示。

### OPS-02｜Outbox 与 Worker 恢复

重复上报、失败重试、租约、死信和审计。
