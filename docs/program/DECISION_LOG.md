# 山水智鉴 — 决策日志

> 记录项目级架构决策和 Agent 间约定。
> 按时间顺序排列，每项决策永久保留。

---

## GOV-02 治理基线 (2026-07-26)

### D-AGENT-001: 五 Agent 编制

- **决策**: 正式采用五 Agent 编制（A/B/C/D/E）
- **理由**: 按领域职责拆分，避免单一 Agent 跨域修改
- **影响范围**: AGENTS.md, agents/, docs/program/
- **决策者**: 项目经理_AGENT_E
- **状态**: ✅ 生效

### D-AGENT-002: 分支策略

- **决策**: 基于 `integration/g0-g1-contract-freeze` 的 clean branch 策略
- **理由**: 避免旧混合分支污染 integration
- **影响范围**: 所有 Git 分支
- **决策者**: 项目经理_AGENT_E
- **状态**: ✅ 生效

### D-AGENT-003: 合并顺序

- **决策**: 固定合并顺序 E → B → A → C → D → E → Integration E2E → develop → main
- **理由**: 可靠性基线先行，感知算法其次，事件消费第三，前端最后
- **影响范围**: INTEGRATION_PLAN.md
- **决策者**: 项目经理_AGENT_E
- **状态**: ✅ 生效

### D-AGENT-004: 禁止 Octopus Merge

- **决策**: 所有合入必须为单个 Agent 的 clean branch → integration
- **理由**: 混合 merge 引入回归时无法追溯责任 Agent
- **影响范围**: 合并流程
- **决策者**: 项目经理_AGENT_E
- **状态**: ✅ 生效

### D-AGENT-005: Integration 基线定位

- **决策**: `integration/g0-g1-contract-freeze` 作为 G0-G1 阶段的唯一集成门禁基线
- **理由**: 将合同冻结与旧 Agent 分支解耦
- **影响范围**: 分支策略、开发流程
- **决策者**: 项目经理_AGENT_E
- **状态**: ✅ 生效

---

## 历史决策（来自 山水智鉴_项目驾驶舱.md）

| ID | 决策 | 状态 |
|:--:|------|:----:|
| D-001 | 产品治理链与比赛评测链硬隔离 | ✅ 生效 |
| D-002 | DetectionResult 仅保留为 V0 兼容对象 | ✅ 生效 |
| D-003 | 产品链正式对象：Observation → Candidate → Event → Review | ✅ 生效 |
| D-004 | 比赛链正式对象：InferenceTask → PredictionRecord → SubmissionBundle | ✅ 生效 |
| D-005 | 两链只共享资产、模型运行、预处理与版本信息 | ✅ 生效 |
| D-006 | V0 继续采用模块化单体，不提前拆微服务 | ✅ 生效 |
| D-007 | SQLite 保留到 V0 完成 | ✅ 生效 |
| D-008 | Jinja2 页面保留为可运行演示，React 迁移不得阻塞算法 | ✅ 生效 |
| D-009 | 现有工单页保留为 legacy demo，P0 不扩展完整工单中心 | ✅ 生效 |
| D-010 | 高点视频先做单视频纵切，不先建多路实时平台 | ✅ 生效 |
| D-011 | 遥感候选不称政府认定异常，保留"变化候选/待研判"语义 | ✅ 生效 |
| D-012 | 507 条候选不作为精度指标 | ✅ 生效 |
| D-013 | COG + TiTiler 只有真实瓦片加载通过后才算完成 | ✅ 生效 |
| D-014 | 官方数据开放前冻结接口，不提前冻结最终模型框架 | ✅ 生效 |
