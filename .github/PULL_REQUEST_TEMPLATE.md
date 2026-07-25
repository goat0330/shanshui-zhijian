---
name: Pull Request
about: 提交 Agent 工作分支到 integration
title: '[agent:X] <简要描述>'
labels: ''
assignees: ''
---

## Agent 信息

- **Agent**: [A/B/C/D/E]
- **Work Package**: [工作包 ID]
- **分支**: [branch name]
- **基线 Commit**: [integration/g0-g1-contract-freeze HEAD]

## 业务目标

[简述此 PR 解决什么业务问题]

## 修改文件清单

[列出此 PR 修改的文件，按目录分组]

### 允许目录
- `allowed/dir/`

### 禁止目录检查
- [ ] 确认未修改禁止目录文件
- [ ] 如修改了禁止目录文件，说明理由并附 Agent 咨询记录

## 合同变更

- [ ] 未修改共享合同
- [ ] 修改了以下共享合同：
  - [合同名] — 变更内容：[...] — 下游 Agent：[...]

## 测试

- [ ] 测试已通过（`pytest ...`）
- [ ] 测试覆盖了新增/修改场景
- [ ] 无 skip 测试
- [ ] 回归测试通过

## 真实数据验证

- [ ] 已完成真实数据运行
- [ ] 运行摘要已附

## Gate 检查清单

[参考 RELEASE_GATE.md 中对应 Agent 的 Gate 条件，逐项确认]

| # | 条件 | 状态 |
|:-:|------|:----:|
| 1 | [...] | ✅ / ❌ |

## 下游 Agent 兼容性

[此 PR 是否影响下游 Agent？如影响，通知了哪些 Agent？]

## 附件

- [运行摘要]
- [Gate 检查清单截图]
- [真实数据验证结果]
