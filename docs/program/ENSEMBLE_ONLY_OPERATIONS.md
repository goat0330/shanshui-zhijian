# Ensemble-only Session 控制手册

## 目的

Ensemble 是本项目唯一的动态 Session 控制平面。长期可见的 A/B/C/D/E
Session 仍由人类直接进入和对话；Ensemble child session 用于短周期并行任务、
审计和协作，不自动接管旧 Session。

## 当前正式配置

- 活动插件：`@hueyexe/opencode-ensemble@0.15.2`
- OMO：不在活动插件列表；仅保留回滚备份和非活动依赖
- 正式配置：`C:\Users\WangChi\.claude\geocode\opencode.json`
- Ensemble 策略：`C:\Users\WangChi\.claude\geocode\.opencode\ensemble.json`
- 策略要求：`mergeOnCleanup: false`
- 正式启动器：`C:\Users\WangChi\.claude\geocode\_launch.ps1`
- 回滚备份：`C:\Users\WangChi\.claude\geocode\backup-ensemble-switch-20260726-145024`

## Agent 参数规则

`team_spawn` 的 `agent` 参数必须是当前 OpenCode 中真实存在的 key：

| 任务 | 允许 key |
|---|---|
| 写入、编码、测试 | `build` |
| 只读计划审计 | `plan` |
| 只读探索 | `explore` |

禁止传入 `general`、`Sisyphus`、`ultraworker` 或岗位中文名。岗位显示名通过
`name` 参数表达，例如 `感知算法_AGENT_A`。OMO 的 `general` 映射可能在初始
prompt 或后续唤醒阶段崩溃。

## 唤醒验收

必须把两个结果分开记录：

1. 成员仍为 `working`，`team_message` 后收到带 nonce 的新回复：唤醒通过。
2. 成员已经完成或 shutdown，消息只进入历史且不唤醒：这是预期行为，不判为故障。

每次验收至少记录：成员状态、使用的 agent key、nonce、`team_status`、
`team_results`、是否有异常重试和是否修改文件。

## 固定岗位与动态启停

固定 Agent ID 不变：

`PERCEPTION_AGENT_A`、`RELIABILITY_AGENT_B`、`EVENT_AGENT_C`、
`WORKBENCH_AGENT_D`、`PROGRAM_AGENT_E`。

每轮可只启用 1—4 个执行成员；改变职责时签发新的 Work Package，更新允许目录、
输入/输出合同和 Gate，不创建新的岗位 ID。人类始终拥有 integration、develop、
main 的最终合并权。

## 回滚

关闭 GeoCode 后，将正式 `opencode.json`、`tui.json`、`package.json` 和
`package-lock.json` 从备份恢复；不要删除项目 worktree、recovery branch 或
bundle。恢复后重新启动并检查活动插件列表。
