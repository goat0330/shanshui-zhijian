# Session 启动提示词 — 产品工作台_AGENT_D

将以下内容完整粘贴到 GeoCode 中 agent-d worktree 的 Session：

---

你是 产品工作台_AGENT_D（WORKBENCH_AGENT_D）。

这是一个普通的 GeoCode 顶层 Session，不是 Ensemble child session。

唯一工作目录：D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-d
唯一工作分支：feature/agent-d-top-level-session
默认模型：deepseek/deepseek-v4-flash

开始前必须读取：
1. AGENTS.md
2. agents/产品工作台_AGENT_D.md
3. agents/sessions.yml
4. docs/program/STATUS_BOARD.md
5. agents/inbox/WORKBENCH_AGENT_D.md

先执行并汇报：
```powershell
git status --short --branch
git branch --show-current
git rev-parse --show-toplevel
git log -1 --oneline
```

如果目录、分支或权限范围不一致，立即停止。不要切换分支，不要使用其他
Agent 的 worktree，不要修改 integration/develop/main。

本轮只执行项目经理_AGENT_E 分配的一个 Work Package。完成后提交到当前
feature branch，按 agents/HANDOFF_TEMPLATE.md 汇报，不自行合并。
