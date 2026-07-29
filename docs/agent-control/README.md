# Agent Control Workflow

这套控制面适合 Git + OpenCode/Ensemble 多 Agent 项目。它解决的是项目层的
路由、门禁、报告压缩和预算预警；不替代 OpenCode Runtime 的原生 compact、
历史存储或 Team Lead 转移能力。

## 每轮工作流

```text
preflight
→ frozen config
→ explicit base
→ parallel work packages
→ compact agent reports
→ ensemble-efficiency
→ Owner 回退 / E 升级
→ Cycle Gate
→ cycle-close
```

## 启动命令

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> preflight --json
python C:/Users/WangChi/.agents/skills/ensemble-efficiency/scripts/ensemble_efficiency.py --repo <absolute-repo-root> --base <fixed-base> --owner <owner> --task-id <id> --json
```

## 新项目迁移

必须替换：

- `base_branch` 和 frozen base commit；
- A/B/C/D/E Owner；
- domain paths 与 stable files；
- `minimum_checks` 和 CI/E2E 命令；
- Team 名称、Branch 和 Worktree 规则。

核心脚本可以复用，但配置不能直接复制。建议后续增加
`project-profile.schema.json` 和生成器，避免手工维护两份配置。

## Runtime 限制

- 预算预警会生成 handoff，但不会直接调用 OpenCode native compact；
- Skill 不能阻止 OpenChamber 已保存历史被 Runtime 重发；
- Team Lead 轮换必须由支持 Actor/Session Epoch 的 Runtime Adapter 完成；
- 没有 Runtime Adapter 时，保持当前 Lead，短 Cycle 运行并在限制前 compact。
