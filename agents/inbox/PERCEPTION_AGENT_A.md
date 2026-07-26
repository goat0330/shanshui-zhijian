# Inbox: 感知算法_AGENT_A (PERCEPTION_AGENT_A)

> 项目经理_AGENT_E 通过此文件向 A 派发工作。
> 每个 Work Package 必须包含：ID、基线 Commit、业务目标、允许/禁止目录、输入/输出合同、Gate、停止条件。

---

**当前无待办工作包。**

## Work Package 模板

```yaml
wp_id: WP-A-NNN
baseline: integration/g0-g1-contract-freeze@<commit>
objective: >
  一句话描述本轮业务目标
allowed_dirs:
  - tools/
  - core/schemas/contracts/candidate.py
  - core/schemas/contracts/perception.py
forbidden_dirs:
  - frontend/
  - apps/
  - services/
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
