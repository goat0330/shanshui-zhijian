# 五 Session 运行手册

## 1. 组织关系

用户是最终决策人和 Merge Gate Owner。项目经理_AGENT_E 是长期控制面
Session；A、B、C、D 是长期执行 Session。E 可以派单、审计和给出
`MERGE_READY`，但没有用户批准不得合并 integration、develop 或 main。

## 2. 固定映射

| Session | Worktree | Branch |
|---|---|---|
| 感知算法_AGENT_A | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-a` | `feature/agent-a-candidate-clean` |
| 工程可靠性_AGENT_B | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-b` | `feature/agent-b-reliability-repair` |
| 事件治理_AGENT_C | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-c` | `feature/agent-c-event-clean` |
| 产品工作台_AGENT_D | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-d` | `feature/agent-d-workbench-clean` |
| 项目经理_AGENT_E | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-e` | `feature/agent-e-integration-control` |

旧目录 `8.1开始_山水智鉴比赛` 是只读恢复现场。不得继续让多个 Session
在该目录写代码。

## 3. 每次启动的四项检查

```powershell
git status --short --branch
git branch --show-current
git rev-parse --show-toplevel
git log -1 --oneline
```

若目录或分支与上表不一致，立即停止。若工作区包含不属于本 Session 的
改动，也立即停止并通知项目经理_AGENT_E。

## 4. 任务协议

E 派单必须包含：Work Package、基线 Commit、允许/禁止目录、输入/输出
合同、测试命令、Gate、停止条件和下游 Agent。执行 Agent 完成后使用
`agents/HANDOFF_TEMPLATE.md` 汇报 Commit、测试、风险和待办。

## 5. Git 流程

执行 Agent 只在自己的 feature branch 提交和推送。E 依次审查 B、A、C、
D；每次只处理一个候选合并，并在临时集成视图运行全量验证。未经用户
批准，不执行正式 integration 合并。

## 6. OpenCode Ensemble 边界

Ensemble 仅作为新的隔离试验控制面使用，不接管或改写旧 Session 数据。
配置必须固定 `mergeOnCleanup: false`。禁止 `team_merge`；成员只提交、
推送、发送 handoff。任何自动创建 worktree 的结果都要先检查路径和分支。

## 7. 故障恢复

共享目录事故的只读恢复点：

`recovery/shared-worktree-event-c-20260726-104210`

备份 Bundle：

`D:\研究生作业\人工智能实践比赛\山水智鉴_多Session恢复备份\recovery_shared-worktree-event-c-20260726-104210.bundle`

不得删除旧目录、recovery branch 或 bundle，直到 v0.1.0 发布且用户确认。
