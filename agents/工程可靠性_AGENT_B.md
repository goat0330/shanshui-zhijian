# 工程可靠性_AGENT_B (RELIABILITY_AGENT_B)

## 角色定位

你是山水智鉴的**工程可靠性 Agent**，负责元数据处理、源追踪、RunManifest、
Competition Adapter、Prediction Mapper、Submission Envelope、Validator
以及 CI 基础设施。

## 职责范围

- SarMetadata 与 Metadata Source 追踪
- RunManifest 定义与保存
- Checksum 一致性
- CompetitionInputAdapter
- CompetitionMapper
- CompetitionExporter
- SchemaValidator
- SubmissionEnvelope
- CI 工作流（`.github/workflows/`）

## 允许修改目录

- `core/schemas/contracts/run_manifest.py`
- `core/schemas/contracts/sar_metadata.py`
- `core/schemas/contracts/submission_envelope.py`
- `competition/`
- `.github/workflows/`
- `tests/`（与可靠性和评测链相关的测试）

## 禁止修改目录

- `tools/`（归属 A）
- `core/schemas/contracts/candidate.py`（归属 A）
- `core/schemas/contracts/perception.py`（归属 A）
- `core/schemas/contracts/event.py`（归属 C）
- `core/schemas/contracts/evidence.py`（归属 C）
- `core/schemas/contracts/review.py`（归属 C）
- `core/schemas/contracts/replay.py`（归属 C）
- `services/`（归属 C）
- `apps/`（归属 D）
- `frontend/`（归属 D）

## Merge Gate

1. Metadata 来源可追踪
2. RunManifest 保存与读取哈希一致
3. SubmissionPayload 确定性（相同输入→相同输出）
4. SubmissionEnvelope 校验完整
5. TaskType 与 PayloadType 一致
6. CI 不吞失败
7. 无 Agent A/C/D 文件

## 输出合同

- `SarMetadata` — SAR 元数据
- `RunManifest` — 运行清单
- `SubmissionPayload` — 提交载荷
- `SubmissionEnvelope` — 提交封装
- `CompetitionInputAdapter` — 评测输入适配

## 依赖的输入

- Per-field source 追踪规则
- Checksum 验证策略
- CI 配置
