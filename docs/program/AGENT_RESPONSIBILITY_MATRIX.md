# Agent 责任矩阵

> 定义每个目录/文件/合同的责任 Agent。
> R=负责 (Responsible), A=审批 (Approves), C=咨询 (Consulted), I=知情 (Informed)

---

## 目录所有权矩阵

| 目录 | A | B | C | D | E |
|------|:-:|:-:|:-:|:-:|:-:|
| `tools/` | **R** | I | - | - | - |
| `core/protocols/` | **R** | C | - | - | - |
| `core/schemas/contracts/candidate.py` | **R** | C | C | - | A |
| `core/schemas/contracts/perception.py` | **R** | - | - | - | - |
| `core/schemas/contracts/run_manifest.py` | C | **R** | - | - | A |
| `core/schemas/contracts/sar_metadata.py` | C | **R** | - | - | - |
| `core/schemas/contracts/submission_envelope.py` | - | **R** | - | - | - |
| `core/schemas/contracts/event.py` | - | - | **R** | - | A |
| `core/schemas/contracts/evidence.py` | - | - | **R** | - | A |
| `core/schemas/contracts/review.py` | - | - | **R** | - | - |
| `core/schemas/contracts/replay.py` | - | - | **R** | - | - |
| `competition/` | - | **R** | - | - | I |
| `services/` | - | - | **R** | C | I |
| `apps/workbench_api/` | - | - | - | **R** | I |
| `frontend/` | - | - | - | **R** | I |
| `docs/program/` | - | - | - | - | **R** |
| `docs/product/` | C | C | C | **R** | A |
| `ml/` | - | - | - | - | **R** |
| `.github/workflows/ci.yml` | - | **R** | - | - | A |
| `AGENTS.md` | I | I | I | I | **R** |
| `山水智鉴_项目驾驶舱.md` | I | I | I | I | **R** |

## 关键合同所有权

| 合同 | 所有者 | 修改流程 |
|------|--------|----------|
| `AssetRef` | A | A 修改，B/C/D 咨询 |
| `Observation` | A | A 修改 |
| `DetectionCandidate` | A | A 修改，C（消费方）评审 |
| `SarMetadata` | B | B 修改，A（生产方）咨询 |
| `RunManifest` | B | B 修改 |
| `SubmissionEnvelope` | B | B 修改 |
| `Evidence` | C | C 修改 |
| `Event` | C | C 修改 |
| `Review` | C | C 修改 |
| `Replay` | C | C 修改 |
| `ModelArtifact` | E | E 定义，A 实施 |
