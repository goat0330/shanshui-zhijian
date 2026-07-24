# Git 分支与交付规范

## 1. 分支职责

| 分支 | 职责 |
|---|---|
| `main` | 稳定、可运行、文档与代码一致 |
| `develop` | 集成最新完成项 |
| `feature/*` | 单个工作包 |
| `fix/*` | 缺陷 |
| `docs/*` | 文档、ADR 和状态 |
| `experiment/*` | 可丢弃实验 |

## 2. 推荐同步动作

当前公开 `main` 与最新 `develop` 状态不一致，应：

1. 从 `develop` 创建同步 PR；
2. 在 PR 中列出新增代码、测试、数据结构和已知问题；
3. README、驾驶舱与状态文档同 PR 更新；
4. 合并后创建 `v0.1.0-rs-prototype` 标签；
5. 后续所有功能走小 PR。

## 3. 一个 PR 只解决一个主题

建议拆分：

- `docs/architecture-v1`；
- `feature/rs-validation-set`；
- `fix/titiler-route-prefix`；
- `feature/competition-prediction-record`；
- `feature/domain-compat-adapter`；
- `feature/video-minimal-slice`。

不要在同一个 PR 同时进行数据库迁移、前端重写和模型优化。

## 4. 合并要求

- 测试通过；
- 无数据和密钥；
- 文档说明当前实现与目标设计；
- Schema 修改有示例和兼容说明；
- 评测输出修改有 golden test；
- 遥感实验有 Run Manifest 和指标；
- UI 修改有截图或 E2E；
- 失败时可回滚。

## 5. Agent 工作方式

每个 Agent 领取一个 Issue，并在独立分支工作。交付必须包含：

```text
Issue
→ 分支
→ 修改文件
→ 测试命令
→ 结果
→ 已知限制
→ PR
```

跨 Agent 依赖通过 Schema、Issue 和 PR 传递，不通过复制聊天记录传递。
