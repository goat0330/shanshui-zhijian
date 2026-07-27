# 山水智鉴 — 发布门禁 (Release Gate)

> 定义每个 Agent 提交至 integration、最终发布和产品验收的 Gate 条件。

---

## 第 0 步：GOV Governance Bootstrap Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Markdown 链接有效 | 手动检查 |
| 2 | YAML 可解析 | `python -c "import yaml; yaml.safe_load(open(...))"` |
| 3 | Agent 名称一致 | 全文一致性检查 |
| 4 | Branch 名称一致 | 文档与分支名匹配 |
| 5 | README、驾驶舱、Status Board 状态一致 | 交叉检查 |
| 6 | 没有修改 A/B/C/D 领域代码 | `git diff --name-only` vs 禁止目录 |

---

## 第 1 步：工程可靠性_AGENT_B Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | 环境预检脚本可重复执行 | `pwsh -File scripts/preflight.ps1` |
| 2 | PROJ/GDAL 污染可会话隔离 | conftest.py 弹出环境变量 |
| 3 | pytest 不依赖外部 PostgreSQL PROJ | clean env → pytest collection |
| 4 | CI preflight 工作流通过 | GitHub Actions 检查 |
| 5 | 无 Agent A/C/D 文件 | `git diff --name-only integration...branch` |

---

## 第 2 步：感知算法_AGENT_A Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Candidate v0.3 冻结 | Schema 版本标记为 v0.3 |
| 2 | Observation→Candidate 完整 | ID 与 Track ID 语义明确 |
| 3 | 双时相冻结回归不变 | regression test |
| 4 | 多时相测试通过 | test_rs01b2 |
| 5 | 持续性测试通过 | test_rs01b3 |
| 6 | ModelArtifact 接口明确 | 接口文档 |
| 7 | 无 Agent B/C/D 文件 | `git diff --name-only` |

---

## 第 3 步：事件治理_AGENT_C Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | 第一次 intake 正常 | e2e test |
| 2 | 重试幂等 | 重复 intake 返回相同结果 |
| 3 | transaction 原子 | 部分失败回滚 |
| 4 | Event v1/v2 都可查询 | 版本兼容测试 |
| 5 | Review 乐观锁 | 并发审核测试 |
| 6 | Replay 不重复 | 重复 Replay 返回相同结果 |
| 7 | Candidate 不被修改 | 只读消费验证 |
| 8 | 无 Agent A/B/D 文件 | `git diff --name-only` |

---

## 第 4 步：产品工作台_AGENT_D Gate

### Engine Gate（工程门禁）

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Mock/Real 双模式 | 统一 Provider Interface 切换 |
| 2 | OpenAPI 类型生成 | Client 类型与 Schema 一致 |
| 3 | Layer Registry | 注册+查询正常 |
| 4 | Candidate→Review→Event→Replay | 全流程 E2E |
| 5 | Run 追溯 | RunCenter 显示历史 |
| 6 | Playwright | E2E 测试通过 |
| 7 | 不修改领域合同 | `git diff --name-only` |

### Product Gate D0：信息架构

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | 页面结构图提交 | 用户 |
| 2 | 路由（/workbench /dashboard /events /runs /settings） | 用户 |
| 3 | 组件树 | 用户 |
| 4 | 用户流程 | 用户 |
| 5 | 研判工作台操作逻辑符合业务 | 用户 |
| 6 | 领导驾驶舱展示内容符合比赛 | 用户 |
| 7 | 两个入口边界清楚 | 用户 |

### Product Gate D1：组件与视觉基础

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | Design Tokens | 用户 |
| 2 | Candidate Card | 用户 |
| 3 | 状态标签 | 用户 |
| 4 | 地图工具栏 | 用户 |
| 5 | 数据卡片 | 用户 |
| 6 | 趋势图 | 用户 |
| 7 | 空/错误/加载状态 | 用户 |

用户验收：信息密度、视觉方向、文案、状态色、组件是否适合工作台+驾驶舱复用。

### Product Gate D2：Mock 可操作原型

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | /workbench 可操作 | 用户 |
| 2 | /dashboard 展示真实内容 | 用户 |
| 3 | /events 可查看 | 用户 |
| 4 | /runs 可查看 | 用户 |
| 5 | 点 Candidate → 地图定位 | 用户 |
| 6 | 切换图层 | 用户 |
| 7 | 提交 Mock Review | 用户 |
| 8 | 查看 Event | 用户 |
| 9 | 领导驾驶舱刷新展示变化 | 用户 |
| 10 | 典型案例播放 | 用户 |

### Product Gate D3：真实 API 集成

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | 真实数据与 Mock 数据表现一致 | 用户 |
| 2 | 操作顺畅 | 用户 |
| 3 | 错误提示明确 | 用户 |
| 4 | 驾驶舱指标来自真实数据 | 用户 |
| 5 | 适合比赛演示 | 用户 |

未经用户的 Product Gate，不得冻结最终页面布局和视觉。

---

## 第 5 步：项目经理_AGENT_E ML Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Dataset Registry | 完成所有数据集记录 |
| 2 | License Matrix | 所有许可证可商用/比赛 |
| 3 | Split Policy | Train/Val/Test 不泄漏 |
| 4 | 本地代理验证集 | 可重复加载与评估 |
| 5 | 规则 Baseline 冻结 | 指标固定 |
| 6 | 训练 Pipeline 可复现 | 相同配置→相同指标 |
| 7 | ModelArtifact | 规范定义 |
| 8 | 不修改 A/B/C/D 领域代码 | `git diff --name-only` |

---

## 返工机制

每个 Agent 提交后执行：

```
Agent 自检
→ 项目经理_AGENT_E 工程 Review
→ 用户产品验收（如适用）
→ integration
```

未通过时：

| 裁决 | 含义 |
|------|------|
| `RETURN_TO_AGENT_A` | A 的问题由 A 返工 |
| `RETURN_TO_AGENT_B` | B 的问题由 B 返工 |
| `RETURN_TO_AGENT_C` | C 的问题由 C 返工 |
| `RETURN_TO_AGENT_D` | D 的问题由 D 返工 |
| `RETURN_TO_AGENT_E` | 治理问题由 E 返工 |

规则：
- E 不能替其他 Agent 修改其所有权代码
- 跨合同冲突由 E 组织联合修复，但文件所有者负责提交
- 产品验收失败 = `RETURN_TO_AGENT_D` + `RETURN_TO_PROMPT_DESIGN`

---

## 最终发布审查 (Final Release Review)

`RC-01` 候选必须经过以下完整审查。

### 1. 项目经理_AGENT_E 工程审查

| # | 检查项 | 方法 |
|:-:|--------|------|
| 1 | 所有 Agent Gate 通过 | Gate 检查清单 |
| 2 | 全量测试通过 | `pytest tests/` exit 0 |
| 3 | CI 全部 green | GitHub Actions |
| 4 | 无 blocking issue | Issue tracker |
| 5 | 所有合同 schema 冻结 | Schema 版本号 |
| 6 | 文档一致 | 交叉检查 |
| 7 | 真实 AOI 数据验证 | 实际运行摘要 |
| 8 | 产品演示可运行 | Playwright E2E |
| 9 | 各 Worktree 干净 | `git worktree list --porcelain` |
| 10 | 各 Branch 已提交已推送 | `git branch -vv` / `git log --oneline --decorate` |

### 2. 用户产品验收

用户实际操作：
- 研判工作台全流程
- 领导驾驶舱展示
- 比赛演示路径
- 异常场景（空数据、错误、网络中断）

### 3. 最终 GitHub Review（发布前必过）

由用户执行：
- 每个分支的 Commit 和 diff
- PR 状态和 CI 结果
- 代码质量
- 测试覆盖
- 文档一致性
- 许可证合规
- 安全审计

不满足时 → `CHANGES_REQUIRED`
满足时 → `MERGE_READY_TO_MAIN`

---

## 合并权限

| 操作 | 权限 |
|------|------|
| Clean PR → integration | 用户授权 E 执行 |
| integration → develop | 用户确认 |
| develop → main | 用户确认（完整 GitHub Review 后） |

---

## 决策状态

| 状态 | 含义 |
|------|------|
| `MERGE_READY_TO_INTEGRATION` | 可合入 integration |
| `NOT_READY_TO_INTEGRATION` | 不可合入 |
| `MERGE_READY_TO_DEVELOP` | 可合入 develop |
| `NOT_READY_TO_DEVELOP` | 不可合入 |
| `MERGE_READY_TO_MAIN` | 可发布 |
| `NOT_READY_TO_MAIN` | 不可发布 |
| `PUBLIC_PRETRAINING_READY` | 可开始公开数据预训练 |
| `PUBLIC_PRETRAINING_NOT_READY` | 不可开始 |
