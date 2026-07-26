# GeoCode 持久化多 Agent 运行手册

> 唯一现行 Session SOP。旧顶层 Session 方案已废止，历史可从 Git 获取。

## 1. 正式运行形态

```text
用户（最终决策与 Merge Gate）
└── 项目经理_AGENT_E（GeoCode 顶层 Session）
    ├── perception-agent-a（持久化 child Session + 独立 worktree）
    ├── engineering-agent-b（持久化 child Session + 独立 worktree）
    ├── event-agent-c（持久化 child Session + 独立 worktree）
    └── product-agent-d（持久化 child Session + 独立 worktree）
```

PROGRAM_AGENT_E 是唯一顶层控制面 Session。A/B/C/D 是持久化 Ensemble
child Session。用户可以从侧栏进入 A/B/C/D 直接对话；E 使用 `team_message`、
`team_status`、`team_results` 和 `team_view` 编排成员。

重启后先激活团队；若成员未恢复，调用 `team_reconcile`，不得重复 spawn
同名成员。

## 2. 启动前提

GeoCode 必须打开正式项目根目录：

`D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\integration`

启动 E 前确认：

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short
git log -1 --oneline
```

期望仓库为 `integration` 根目录，分支为 `integration/g0-g1-contract-freeze`，
工作树无未归属修改。

## 3. Team 与成员参数

- Team：`shanshui-zhijian-dev`
- `persistent: true`
- A/B/C/D：`agent=build`
- `worktree=true`
- `model=deepseek/deepseek-v4-flash`
- `mergeOnCleanup=false`
- 禁止 `general`、`Sisyphus`、`ultraworker`

每个成员只 spawn 一次。允许只启用 1—4 个成员；未参与本轮的成员保持 idle。

## 4. Worktree 路径

目标 Worktree 路径：

| 成员 | 期望路径 |
|------|----------|
| perception-agent-a | `..\subsessions\agent-a` |
| engineering-agent-b | `..\subsessions\agent-b` |
| event-agent-c | `..\subsessions\agent-c` |
| product-agent-d | `..\subsessions\agent-d` |

如 Ensemble 自动生成 Worktree，不得手工移动或重命名生成目录。记录其真实
绝对路径并更新 `agents/sessions.yml`。确认四个路径互不相同，且均不等于
integration 根目录或旧 worktree（`agent-a/` ~ `agent-e/`）。

## 5. Worktree 验收

成员第一次响应必须报告：

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short
git log -1 --oneline
```

E 必须确认四个成员的 repo root 和 branch 均互不相同，且都不是
`integration/g0-g1-contract-freeze`、`develop` 或 `main`。
未通过前禁止写代码。成员不得 `git switch`，不得读取或修改其他成员 worktree。

## 6. 旧 Worktree 与目录

以下旧目录已退出正式开发体系，保留为只读恢复现场：

| 目录 | 状态 | 说明 |
|------|------|------|
| `D:\...\8.1开始_山水智鉴比赛` | BLOCKED_DIRTY | 旧 checkout，保留不动 |
| `D:\...\agent-a` — `agent-e` | 已移除 | 旧顶层 Session worktree，已 archive |
| `D:\...\codex-top-level-session` | 已移除 | 旧治理 branch worktree，已 archive |
| `recovery/...` branch | KEEP_RECOVERY | 保留不动 |
| `archive/legacy-*` branch | 只读存档 | 在远端 GitHub 可查询 |

## 7. 派单与回收

E 每次只向一个成员派发一个 Work Package，内容必须包含：基线 Commit、目标、
允许/禁止目录、输入/输出合同、测试、Gate、停止条件和下游 Agent。正式任务单
写入 `agents/inbox/`，运行时通过 `team_message` 发送。

成员完成后：
1. 在自己的 Ensemble worktree 分支提交
2. 按 `agents/HANDOFF_TEMPLATE.md` 返回 Commit、测试、风险和未完成项
3. 进入 idle，等待 E Review
4. 不调用 merge、cleanup 或 shutdown

## 8. 合并权限

E 可以审计 diff、运行集成测试并给出 `MERGE_READY`。没有用户明确批准：
- 不调用 `team_merge`
- 不执行 `team_cleanup`
- 不合并 integration、develop、main
- 不删除 child Session、worktree、recovery branch 或 bundle

一次只审核一个成员分支，推荐依赖顺序为 B → A → C → D；如果工作包之间没有
合同依赖，E 可以建议并行开发，但合并仍串行。

## 9. 重启与清理

重启后：
1. 打开同一正式项目根目录
2. 激活 `shanshui-zhijian-dev`
3. 查看 `team_status`
4. 必要时调用一次 `team_reconcile`
5. 检查侧栏、历史、成员 worktree 和 branch
6. 缺失成员才允许重新 spawn

`team_shutdown` 只停止执行，不删除会话。`team_cleanup` 会归档成员并清理团队，
只在项目阶段结束且用户批准时使用。

## 10. 状态源

- 实时 Session 状态：`http://127.0.0.1:4747/`
- 正式配置：`agents/sessions.yml`
- 人类可读状态：`docs/program/STATUS_BOARD.md`
- 角色边界：`agents/*_AGENT_*.md`
- 决策记录：`docs/program/DECISION_LOG.md`
- 代码事实：Git Commit、PR、CI 和测试日志

Dashboard 只表示运行状态，不替代 Git、CI 或 Merge Gate。
