# 山水智鉴 — 发布门禁 (Release Gate)

> 定义每个 Agent 提交至 integration、产品验收和最终发布的 Gate 条件。

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
| 7 | 未提交本机绝对路径/用户名/临时 Worktree hash | 搜索 `C:\\Users` `\.local\\share\\geocode` 等 |
| 8 | `agents/sessions.local.yml` 在 `.gitignore` | `git ls-files --ignored` |

---

## 第 1 步：工程可靠性_AGENT_B Gate

### B-REL-02｜工作包 Gate（当前 P1）

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | `scripts/preflight.ps1` 可重复执行 | `pwsh -File scripts/preflight.ps1` |
| 2 | PROJ/GDAL 污染可会话隔离 | `tests/conftest.py` 弹出环境变量 |
| 3 | pytest 不依赖外部 PostgreSQL PROJ | clean env → `pytest collection` 成功 |
| 4 | CI preflight 工作流通过 | GitHub Actions 检查 |
| 5 | 文件在正确根目录下（非 `shanshui-zhijian/` 前缀） | `git diff --name-only integration...branch` |
| 6 | 无 Agent A/C/D 文件 | `git diff --name-only integration...branch` |

### B-FINAL｜工程可靠性领域 Gate（P5 集成前通过）

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Metadata per-field source 可追踪 | 每字段有 source 记录 |
| 2 | RunManifest 保存读取哈希一致 | SHA256 验证测试 |
| 3 | Git / config / input / output 血缘可追溯 | RunManifestRecorder Protocol |
| 4 | 输入输出 SHA256 一致性 | Golden test |
| 5 | Competition Adapter 可适配 | test_competition_chain.py |
| 6 | SubmissionPayload 确定性 | 相同输入→相同输出 |
| 7 | SubmissionEnvelope 校验完整 | Schema + golden test |
| 8 | Validator 规则无漏 | Competition Validator tests |
| 9 | CI 不吞失败 | CI 输出检查 |
| 10 | 环境可复现 | Preflight + CI green in clean env |
| 11 | 无 A/C/D 越权文件 | `git diff --name-only integration...branch` |

> REL-02 Gate 仅覆盖 P1 环境隔离。B-FINAL Gate 覆盖完整可靠性领域。
> 已提交代码但未通过 Clean PR + CI 验证的 Agent 自报结果
> 标记为 `AGENT_SELF_REPORTED / PENDING_E_VERIFICATION`。

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
| 1 | 页面结构图提交（/workbench /dashboard /events /runs /settings） | 用户 |
| 2 | 路由表、组件树、用户流程 | 用户 |
| 3 | 研判工作台操作逻辑符合业务 | 用户 |
| 4 | 领导驾驶舱展示内容符合比赛 | 用户 |
| 5 | 两个入口边界清楚 | 用户 |

### Product Gate D1：组件与视觉基础

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | Design Tokens | 用户 |
| 2 | Candidate Card | 用户 |
| 3 | 状态标签 | 用户 |
| 4 | 地图工具栏 | 用户 |
| 5 | 数据卡片、趋势图 | 用户 |
| 6 | 空/错误/加载状态 | 用户 |

用户验收：信息密度、视觉方向、文案、状态色、组件是否适合工作台+驾驶舱复用。

### Product Gate D2：Mock 可操作原型

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | `/workbench` 可操作（Mock 数据） | 用户 |
| 2 | `/dashboard` 使用 **Mock 数据** 完整展示预定业务指标和典型案例 | 用户 |
| 3 | `/events` `/runs` 可查看 | 用户 |
| 4 | 点 Candidate → 地图定位 → 影像对比 → Evidence → Mock Review | 用户 |
| 5 | 切换图层 | 用户 |
| 6 | 驾驶舱随 Mock Review 状态变化刷新 | 用户 |
| 7 | 典型案例演示播放 | 用户 |
| 8 | **页面明确标注 MOCK / DEMO** | 用户 |
| 9 | **不宣称真实治理成效、真实准确率或真实业务统计** | 用户 |
| 10 | Loading / Empty / Error / Success 状态覆盖 | 用户 |

### Product Gate D3：真实 API 集成

| # | 条件 | 验收人 |
|:-:|------|--------|
| 1 | RealApiProvider 切换后真实数据与 Mock 行为一致 | 用户 |
| 2 | 真实 Candidate、Event、Run 数据流通 | 用户 |
| 3 | 驾驶舱指标来自真实数据 | 用户 |
| 4 | 数据来源和更新时间可追溯 | 用户 |
| 5 | 错误处理和网络中断提示明确 | 用户 |
| 6 | 适合比赛演示 | 用户 |

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
Agent 自检 + 自报（标记 PENDING_E_VERIFICATION）
→ 项目经理_AGENT_E 工程 Review + 验证 → VERIFIED
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

RC-01 候选必须经过以下三层审查。

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
| 11 | 无未推送 Commit | `git log --oneline origin/integration..HEAD` |
| 12 | 无本机路径泄露 | 搜索 `C:\\Users` / `\.local\\share` |

### 2. 用户产品验收

用户实际操作：
- 研判工作台全流程
- 领导驾驶舱展示
- 比赛演示路径
- 异常场景（空数据、错误、网络中断）

### 3. 独立架构审查人（INDEPENDENT_RELEASE_REVIEWER）

最终 GitHub Review 由独立架构审查人（当前由 ChatGPT 承担）执行：
- Clone 或通过 GitHub API 读取全仓库代码
- 检查各 Branch、Commit、PR、Diff、CI
- 检查代码质量、架构边界、测试可信度
- 检查文档一致性和许可证合规

输出状态：

| 状态 | 含义 |
|------|------|
| `CHANGES_REQUIRED` | 不可发布，需返工 |
| `MERGE_READY_TO_MAIN` | 可发布至 main |

---

## 合并权限

| 操作 | 权限 | 备注 |
|------|------|------|
| Clean PR → integration | E 已获常规授权，Gate 全通过后可执行 | Product Gate 涉及 D 时须先取得用户验收 |
| integration → develop | 用户确认 | E 输出 MERGE_READY_TO_DEVELOP，用户批准后执行 |
| develop → main | 用户最终确认 | E 完成 RC 审计 + 用户产品验收 + 独立审查人 MERGE_READY_TO_MAIN |

---

## 决策状态

| 状态 | 使用场景 |
|------|----------|
| `MERGE_READY_TO_INTEGRATION` | Clean PR 可通过工程 Gate，可合入 integration |
| `NOT_READY_TO_INTEGRATION` | 不可合入 integration |
| `MERGE_READY_TO_DEVELOP` | 可合入 develop |
| `NOT_READY_TO_DEVELOP` | 不可合入 develop |
| `MERGE_READY_TO_MAIN` | 可发布至 main（用户批准后执行） |
| `NOT_READY_TO_MAIN` | 不可发布 |
| `PUBLIC_PRETRAINING_READY` | 可开始公开数据预训练 |
| `PUBLIC_PRETRAINING_NOT_READY` | 不可开始 |
