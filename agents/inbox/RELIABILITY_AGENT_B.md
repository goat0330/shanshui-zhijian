# Inbox: 工程可靠性_AGENT_B (RELIABILITY_AGENT_B)

> 项目经理_AGENT_E 通过此文件向 B 派发工作。
> 每个 Work Package 必须包含：ID、基线 Commit、业务目标、允许/禁止目录、输入/输出合同、Gate、停止条件。

---

**当前无待办工作包。**

## Work Package 模板

```yaml
wp_id: WP-B-NNN
baseline: integration/g0-g1-contract-freeze@<commit>
objective: >
  一句话描述本轮业务目标
allowed_dirs:
  - core/schemas/contracts/run_manifest.py
  - core/schemas/contracts/sar_metadata.py
  - core/schemas/contracts/submission_envelope.py
  - competition/
  - tests/
forbidden_dirs:
  - frontend/
  - apps/
  - tools/
input_contract:
  - <文件路径>: <说明>
output_contract:
  - <文件路径>: <说明>
required_tests:
  - <测试路径>
gate: <Gate 名称>
stop_condition: <停下的条件>
downstream: <下一个 Agent>
```
