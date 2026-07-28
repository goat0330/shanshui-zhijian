# agents/ — 多 Agent 角色定义

> 本目录包含山水智鉴项目五 Agent 的正式角色定义文件。
> 每份文件是 Agent 的宪章——定义其职责边界、权限目录、禁止目录、Merge Gate 和任务模板。

## 文件清单

| 文件 | Agent | 英文代号 |
|------|-------|----------|
| [感知算法_AGENT_A.md](感知算法_AGENT_A.md) | 感知算法_AGENT_A | PERCEPTION_AGENT_A |
| [工程可靠性_AGENT_B.md](工程可靠性_AGENT_B.md) | 工程可靠性_AGENT_B | RELIABILITY_AGENT_B |
| [事件治理_AGENT_C.md](事件治理_AGENT_C.md) | 事件治理_AGENT_C | EVENT_AGENT_C |
| [产品工作台_AGENT_D.md](产品工作台_AGENT_D.md) | 产品工作台_AGENT_D | WORKBENCH_AGENT_D |
| [项目经理_AGENT_E.md](项目经理_AGENT_E.md) | 项目经理_AGENT_E | PROGRAM_AGENT_E |
| [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md) | — | Agent 交接模板 |

## 使用规则

1. 每份 Agent 文件不得被非所属 Agent 修改；
2. Agent 文件修改必须经过该 Agent 负责人和项目经理_AGENT_E 双重批准；
3. 所有 Agent 之间的接口合同变更必须在 DECISION_LOG.md 记录；
4. 新 Agent 的加入必须更新 AGENTS.md、本 README 和所有相关 Gate 定义。
