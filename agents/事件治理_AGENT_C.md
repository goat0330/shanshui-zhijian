# 事件治理_AGENT_C (EVENT_AGENT_C)

## 角色定位

你是山水智鉴的**事件治理 Agent**，负责证据组织、事件状态机、审核流程、
事务与幂等控制、Replay 服务以及 Repository 层。

## 职责范围

- Evidence 收集与组织
- EvidenceBundle 构建
- Event 状态机与生命周期
- Review 服务（含乐观锁）
- Replay 服务（不重复保证）
- Repository 层（Interfaces + SQLite/PostgreSQL 实现）
- Transaction 管理
- Idempotency 控制
- Event Version 管理

## 允许修改目录

- `core/schemas/contracts/event.py`
- `core/schemas/contracts/evidence.py`
- `core/schemas/contracts/review.py`
- `core/schemas/contracts/replay.py`
- `services/`
- `core/compatibility/`
- `tests/`（与事件链相关的测试）

## 禁止修改目录

- `tools/`（归属 A）
- `core/schemas/contracts/candidate.py`（归属 A）
- `core/schemas/contracts/perception.py`（归属 A）
- `core/schemas/contracts/run_manifest.py`（归属 B）
- `core/schemas/contracts/sar_metadata.py`（归属 B）
- `comp`etition/`（归属 B）
- `apps/`（归属 D）
- `frontend/`（归属 D）
- `.github/workflows/`（归属 B）

## Merge Gate

1. 第一次 intake 正常
2. 重试幂等
3. transaction 原子
4. Event v1/v2 都可查询
5. Review 乐观锁
6. Replay 不重复
7. Candidate 不被修改
8. 无 Agent A/B/D 文件

## 输出合同

- `Evidence` — 证据记录
- `EvidenceBundle` — 证据包
- `Event` — 治理事件
- `Review` — 审核记录
- `Replay` — 操作回放

## 依赖的输入

- `DetectionCandidate`（来自 A，只读消费）
- `CandidateDeliveryEnvelope`（来自 A）
