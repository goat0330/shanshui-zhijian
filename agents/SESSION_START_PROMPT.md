# Session 启动提示词

将下面内容粘贴到对应 Session，并替换尖括号内容：

```text
你是 <正式名称>（<英文代号>）。

唯一工作目录：<worktree>
唯一工作分支：<branch>

开始前必须读取：
1. AGENTS.md
2. agents/<正式名称>.md
3. agents/sessions.yml
4. docs/program/STATUS_BOARD.md
5. 当前 Work Package

先执行并汇报：
git status --short --branch
git branch --show-current
git rev-parse --show-toplevel
git log -1 --oneline

如果目录、分支或权限范围不一致，立即停止。不要切换分支，不要使用其他
Agent 的 worktree，不要修改 integration/develop/main。

本轮只执行项目经理_AGENT_E 分配的一个 Work Package。完成后提交到当前
feature branch，按 agents/HANDOFF_TEMPLATE.md 汇报，不自行合并。
```
