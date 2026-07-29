# Runtime Adapter

这些 TypeScript 模块是 OpenCode Runtime 的安全适配层，不是普通项目脚本。

## 已提供

- `context-compact.ts`：读取 active context，调用 `client.session.compact`，验证视图缩小；
- `actor-session.ts`：通过 compare-and-swap 轮换 Actor 的 Session Epoch；
- `migration-v10.ts`：在 staging SQLite 副本上增加 Actor/Session Epoch 结构；
- `types.ts`：最小 Database/SDK 接口。

## 安全边界

当前默认只允许：

1. disposable OpenCode Session；
2. staging Ensemble database；
3. dry-run 或显式 `--apply` 的适配器调用；
4. 先做 SQLite backup 和 SHA-256 manifest。

禁止直接把这些模块指向 live `ensemble.db`。在生产运行前必须确认：

- OpenChamber 实际加载的 OpenCode 配置和插件包；
- `client.session.context` / `client.session.compact` 可用；
- Actor 与 Session Epoch migration 已在 staging 通过；
- CAS 轮换能阻止旧 Session 写入；
- compact 后 active model view 确实缩小；
- 新 Session 可以继续消费 Team mailbox。

这部分目前是 Runtime Adapter 的实现骨架和 staging 入口，不宣称已经完成生产 Lead Transfer。
