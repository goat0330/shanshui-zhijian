# 山水智鉴 — 发布门禁 (Release Gate)

> 定义每个 Agent 提交至 integration 和最终发布的 Gate 条件。

---

## 第 0 步：GOV-02 Governance Bootstrap Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Markdown 链接有效 | 手动检查 |
| 2 | YAML 可解析 | `python -c "import yaml; yaml.safe_load(open(...))"` |
| 3 | Agent 名称一致 | 全文一致性检查 |
| 4 | Branch 名称一致 | 文档与分支名匹配 |
| 5 | README、驾驶舱、Status Board 状态一致 | 交叉检查 |
| 6 | 没有修改 A/B/C/D 领域代码 | `git diff --name-only` vs 禁止目录 |

## 第 1 步：工程可靠性_AGENT_B Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Metadata 来源可追踪 | 每字段有 per-field source 记录 |
| 2 | RunManifest 保存读取哈希一致 | SHA256 验证测试 |
| 3 | SubmissionPayload 确定性 | 相同输入→相同输出 |
| 4 | SubmissionEnvelope 校验完整 | Schema + golden test |
| 5 | TaskType 与 PayloadType 一致 | 类型检查 |
| 6 | CI 不吞失败 | CI 输出检查 |
| 7 | 无 Agent A/C/D 文件 | `git diff --name-only integration...branch` |

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

## 第 4 步：产品工作台_AGENT_D Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | Mock/Real 双模式 | MSW 切换 |
| 2 | OpenAPI 类型生成 | Client 类型与 Schema 一致 |
| 3 | Layer Registry | 注册+查询正常 |
| 4 | Candidate→Review→Event→Replay | 全流程 E2E |
| 5 | Run 追溯 | RunCenter 显示历史 |
| 6 | Playwright | E2E 测试通过 |
| 7 | 不修改领域合同 | `git diff --name-only` |

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

## 最终 V0.1 Release Gate

| # | 条件 | 验证方法 |
|:-:|------|----------|
| 1 | 所有 Agent Gate 通过 | Gate 检查清单 |
| 2 | 全量测试通过 | `pytest tests/` exit 0 |
| 3 | CI 全部 green | GitHub Actions |
| 4 | 无 blocking issue | Issue tracker |
| 5 | 所有合同 schema 冻结 | Schema 版本号 |
| 6 | README/驾驶舱/文档一致 | 交叉检查 |
| 7 | 真实 AOI 数据验证 | 实际运行摘要 |
| 8 | 产品演示可运行 | Playwright E2E |
