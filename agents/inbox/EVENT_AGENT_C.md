# Inbox: 事件治理_AGENT_C (EVENT_AGENT_C)

> 项目经理_AGENT_E 通过此文件向 C 派发工作。
> 每个 Work Package 必须包含：ID、基线 Commit、业务目标、允许/禁止目录、输入/输出合同、Gate、停止条件。

---

**当前无待办工作包。**

## Work Package 模板

```yaml
wp_id: WP-C-NNN
baseline: integration/g0-g1-contract-freeze@<commit>
objective: >
  一句话描述本轮业务目标
allowed_dirs:
  - core/schemas/contracts/event.py
  - core/schemas/contracts/evidence.py
  - core/schemas/contracts/review.py
  - core/schemas/contracts/replay.py
  - services/
forbidden_dirs:
  - frontend/
  - apps/
  - tools/
  - competition/
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
