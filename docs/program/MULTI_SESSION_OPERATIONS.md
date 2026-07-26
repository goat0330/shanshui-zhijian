# 五 Session 运行手册

## 1. 组织关系

用户是最终决策人和 Merge Gate Owner。项目经理_AGENT_E 是长期控制面
Session；A、B、C、D 是长期执行 Session。E 可以派单、审计和给出
`MERGE_READY`，但没有用户批准不得合并 integration、develop 或 main。

## 2. 固定身份与动态职责

Agent ID、长期 Session 和 worktree 保持稳定；本轮职责、Work Package 和
branch 可以变化。A 可以从遥感转为计算机视觉，前提是 E 重新签发任务单，
更新允许目录、输入输出合同、Gate 和下游交接。

| Session | Worktree | Branch policy |
|---|---|---|
| 感知算法_AGENT_A | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-a` | `feature/agent-a-*` |
| 工程可靠性_AGENT_B | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-b` | `feature/agent-b-*` |
| 事件治理_AGENT_C | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-c` | `feature/agent-c-*` |
| 产品工作台_AGENT_D | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-d` | `feature/agent-d-*` |
| 项目经理_AGENT_E | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-e` | `feature/agent-e-*` |

旧目录 `8.1开始_山水智鉴比赛` 是只读恢复现场。不得继续让多个 Session
在该目录写代码。

## 3. 每次启动的四项检查

```powershell
git status --short --branch
git branch --show-current
git rev-parse --show-toplevel
git log -1 --oneline
```

若目录或分支不符合上表策略，立即停止。若工作区包含不属于本 Session 的
改动，也立即停止并通知项目经理_AGENT_E。

## 4. 动态启停

每轮允许只启用 1 至 4 个执行 Session，不要求 A/B/C/D 全部参与。E 在
`agents/sessions.yml` 中把参加本轮的 Session 标记为 `enabled: true`，
并为其签发 Work Package；未参加者标记为 `enabled: false`、保持 `idle`，
但其长期会话和 worktree 不删除，也不得领取或修改代码。

职责变更不通过改 Agent ID 实现，而通过新任务单实现。任务完成后 Session
回到 `idle`，worktree 保留，branch 在下一轮开始时重新核对。

## 5. 任务协议

E 派单必须包含：Work Package、基线 Commit、允许/禁止目录、输入/输出
合同、测试命令、Gate、停止条件和下游 Agent。执行 Agent 完成后使用
`agents/HANDOFF_TEMPLATE.md` 汇报 Commit、测试、风险和待办。

## 6. Git 流程

执行 Agent 只在自己的 feature branch 提交和推送。E 依次审查 B、A、C、
D；每次只处理一个候选合并，并在临时集成视图运行全量验证。未经用户
批准，不执行正式 integration 合并。

## 7. 两种 Session 交互面

长期 A/B/C/D/E 使用桌面客户端顶层可见 Session，用户可以逐个进入并直接
对话。Ensemble 动态成员是 child session，可通过 `team_view` 进入完整
会话，也可以使用真实 Session ID 继续对话，但不保证显示为桌面左栏顶层条目。

因此长期岗位使用“固定可见 Session”，临时审计和短周期并行任务使用
“Ensemble 动态团队”，两者通过 Git、状态板和 Handoff 汇合。

## 8. OpenCode Ensemble 边界

当前正式控制插件为 `@hueyexe/opencode-ensemble@0.15.2`，OMO 不再作为
正式 Session 控制面的依赖。Ensemble 不接管或改写旧 Session 数据；配置必须
固定 `mergeOnCleanup: false`。禁止 `team_merge`；成员只提交、推送、发送
handoff。任何自动创建 worktree 的结果都要先检查路径和分支。

`team_spawn` 的 `agent` 参数必须使用当前 OpenCode 中真实存在的 key：写入任务
使用 `build`，只读任务使用 `plan` 或 `explore`。禁止使用 OMO 注入的
`general`、`Sisyphus`、`ultraworker` 别名。成员仍为 `working` 时才测试
`team_message` 唤醒；成员完成或 shutdown 后，消息按设计只存储不唤醒。

## 9. 故障恢复

共享目录事故的只读恢复点：

`recovery/shared-worktree-event-c-20260726-104210`

备份 Bundle：

`D:\研究生作业\人工智能实践比赛\山水智鉴_多Session恢复备份\recovery_shared-worktree-event-c-20260726-104210.bundle`

不得删除旧目录、recovery branch 或 bundle，直到 v0.1.0 发布且用户确认。
