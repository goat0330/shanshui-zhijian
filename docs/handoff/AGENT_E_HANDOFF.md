# AGENT_E 交接文档

> **生成时间**: 2026-07-27 (Session 结束)
> **开发者**: 项目经理_AGENT_E（旧会话已结束）
> **接受者**: 新的项目经理_AGENT_E
> **基线**: `integration/g0-g1-contract-freeze @ f96a5eb`

---

## 1. 项目定位

山水智鉴是面向**水域异常感知、证据核验与治理系统集成**的开放中间件，同时服务产品治理链和比赛评测链。

**产品治理链**: Source → Asset → Observation → DetectionCandidate → Evidence → Review → AnomalyEvent → Replay → 外部治理系统

**比赛评测链**: CompetitionInput → InferenceTask → PerceptionResult → PredictionRecord → SubmissionPayload → SubmissionEnvelope → Validator

**最终产品形态**: 双前端入口（研判工作台 + 领导驾驶舱），同一 React 工程共享组件。

---

## 2. 当前阶段

| 项目 | 值 |
|------|-----|
| 集成基线 | `integration/g0-g1-contract-freeze` |
| 最新 Commit | `f96a5eb` — RC-03b |
| 远端同步 | ✅ 已推送，0 ahead / 0 behind |
| 当前阶段 | P4 RC-03（Mock→Real 管线对接） |
| P0 阻断 | 无 |

### 推进顺序

```
P1  ✅ B — 环境隔离 (已合入)
P2A ✅ A — 合同冻结 (已合入)
P2D ✅ D — 组件 Mock 原型 (已合入)
P3  ✅ C — 持久化事件链 (已合入)
P4  🔄 真实 API 接入 (RC-03 进行中)
P5  ⏸ INT-01/02 集成
P6  ⏸ RC-01 发布候选 (审查: CHANGES_REQUIRED)
```

---

## 3. 用户长期治理规则

来源: 用户 m00033、m00744、m00824、多次口头确认。所有规则已通过用户批准。

**[事实来源: 用户已确认]**

1. **Agent 不重复 Spawn** — 每个 Agent ID 只 spawn 一次，不反复销毁重建
2. **完成任务后不 Shutdown** — Agent 完成当前 Work Package 后保持 idle，不调 `team_shutdown`
3. **下一任务使用 `team_reactivate`** — 重启 Agent 用 `team_reactivate(member=name, prompt=...)`，不是 spawn 新成员
4. **正式 Team 不随意 Cleanup** — 不调 `team_cleanup` 清除正式成员
5. **Worktree 和 Branch 长期复用** — Ensemble 自动创建的 worktree 和 branch 长期有效
6. **每轮任务前同步最新 integration** — `git remote add origin ...; git fetch origin; git reset --hard origin/integration/g0-g1-contract-freeze`
7. **Agent 成果必须 Commit → Push → PR → Merge/Cherry-pick** — 经 GitHub PR 合入，非手工复制文件
8. **Agent E 禁止手工复制 Agent 文件** — E 不得在 integration 上直接修 A/B/C/D 所有权的代码。文件所有权见 AGENTS.md §7

---

## 4. 已完成事项（Git 已确认）

### P0 — 治理基础设施

| 事项 | Commit | 分支 | PR | 备注 |
|------|--------|------|:---:|------|
| 旧 worktree 归档清理 | — | — | — | 6 个旧 worktree 已 remove |
| Legacy dirty 备份 | — | — | — | SHA256 已录 |
| governance v4 (PR #15) | `82c0c1f` | `governance/ensemble-subsession-v4` | #15 | Ensemble 多 Session 框架 |
| governance v5 战略 (PR #16) | `0c30965` | `governance/v5-product-strategy` | #16 | 双前端/D0-D3/三层 Review/返工 |

### P1 — B 环境隔离

| 事项 | Commit | 分支 | PR | 备注 |
|------|--------|------|:---:|------|
| 污染定位: PostgreSQL PROJ_LIB/GDAL_DATA | — | — | — | 用户级环境变量，conftest.py 进程级隔离 |
| preflight.ps1 + conftest.py + pyproject.toml + preflight.yml | `71e407f` | `feature/b-rel-02-final` | #17 | 搬运到 integration |

### P2A — A 合同冻结 (RS-03)

| 事项 | Commit | 备注 |
|------|--------|------|
| candidate.py v0.3（CandidateQualitySummary/coordinate_space/track_id） | `6f050f2` | 含 4 个测试文件 |
| perception/candidate/task/prediction schema | `6f050f2` | 4 schema 文件 |
| CONTRACT_GAPS.md | `6f050f2` | 合同缺口登记 |

### P2D — D Mock 原型 (WB-01A)

| 事项 | Commit | 备注 |
|------|--------|------|
| 驾驶舱态势/空间/趋势/漏斗/案例 5 组件 | `bbb26e2` | 含 /dashboard 路由 |
| D2 MOCK/DEMO 合规 | `bbb26e2` | 标注为 Mock |

### P3 — C 事件链 (EVT-02)

| 事项 | Commit | 备注 |
|------|--------|------|
| CandidateIntake + EvidenceBundle + Review 4 动作 | `ba7b276` | 删除旧 services/* 链 |
| Event int 版本 + Replay 时间线 + 乐观锁 | `ba7b276` | 44/44 tests |
| 删除 35 个冗余 e2e 测试 | `ceef1b5` | test_event_chain_e2e.py 精简 |

### P4 — RC-02.1/02.2 真实 API

| 事项 | Commit | 备注 |
|------|--------|------|
| RealApiProvider 不静默回退 Mock | `2f94b44` `3359c80` | D, submit_review/get_events |
| FastAPI TestClient 4 测试 | `a95f7be` `d91f2ed` | B, GET + POST + validation |
| CI lint + 7 jobs (no continue-on-error) | `d91f2ed` | B |
| VITE_API_MODE=mock→real | `315d856` `f038f4b` | D, prod build 371 modules |
| 代码搬运: A+C+D → integration | `40605b7` | PR #18 |
| RC-02 标签 | `249bb05` | rc-02 tag |
| **RC-01 审查结论** | — | CHANGES_REQUIRED (见 #20) |

### P4 — RC-03 真实存储（E 当前最新）

| 事项 | Commit | 备注 |
|------|--------|------|
| candidate_store.py — 36 条真实种子 | `f3f0d54` | 读 C 的 CandidateRecord |
| Evidence → 读 EvidenceBundleRecord | `f96a5eb` | 回退 mock 时 warning |
| EventGeoJSON → 读 GovernedEventRecord | `f96a5eb` | Point Feature |
| Summary → 真实计数 | `f96a5eb` | 不再 mock |
| Runs/Artifacts → 内联内存数据 | **dirty** | replace mock fallback |
| Dashboard 真实 API | **B/D 完成但丢失** | 见下文 |

### 已创建的 PR

| PR | 分支 | 状态 | 内容 |
|:--:|------|:----:|------|
| #15 | `governance/ensemble-subsession-v4` | ✅ merged → `82c0c1f` | Ensemble 框架 |
| #16 | `governance/v5-product-strategy` | ✅ merged → `0c30965` | 双前端/产品 Gate |
| #17 | `feature/b-rel-02-final` | ✅ merged → `54b0185` | B 环境隔离 |
| #18 | `feature/d-wb-01a` | ✅ merged → `40605b7` | A+D 搬运 |
| #19 | — | ✅ merged | C EVT-02 |
| #20 | `integration/g0-g1-contract-freeze→develop` | 🔄 CHANGES_REQUIRED | RC-01 |

---

## 5. 当前 Dirty 文件

**[事实来源: Git 已确认]**

| 文件 | 修改 | 用户确认？ | 建议 |
|------|------|:---------:|------|
| `apps/workbench_api/real_service.py` | Runs/Artifacts: 从 mock 回退改为内联内存数据（8 条 + 16 个 artifact） | ❌ 未确认 | 🔄 **提交或撤销，由新 E 决定** |

该改动是 E 在 RC-03 执行中手工做的，按照「全部改成内联」的用户指示方向。尚未 commit/push。

---

## 6. 正式 Team 状态

**[事实来源: 工具已确认]**

| 成员 | Session | Worktree | Branch | 状态 | 最后任务 |
|:----:|:-------:|----------|--------|:----:|---------|
| A | `ses_05dcf4d24ffe7HqAwG3Z...` | `.../worktree/06214d6125af0bed3558b2598c9f559d8c0eed89/ensemble-...-perception-agent-a` | `opencode/ensemble-...-perception-agent-a` | **working** | E team_reactivate → RS-04 SAR 回归修复 |
| B | — | — | — | **shutdown** | RC-02.1 TestClient + CI lint |
| C | `ses_05dcf4294ffeUN1a7NH1...` | `.../worktree/06214d6125af0bed3558b2598c9f559d8c0eed89/ensemble-...-event-agent-c` | `opencode/ensemble-...-event-agent-c` | **working** | E team_reactivate → EVT-03 Evidence/Summary 增强 |
| D | — | — | — | **shutdown** | RC-02.1 RealApiProvider |
| E (旧) | — | — | — | **结束** | P4 RC-03 真实存储 |

### 丢失的成员（E 错误 shutdown 后不可 reactivate）

| 成员 | 丢失原因 | 丢失成果 |
|:----:|---------|----------|
| B (engineering-agent-b-rc03) | E 调 shutdown + team_merge 失败 | `run_store.py` + `real_service.py` runs 修改（48 tests） |
| D (product-agent-d-rc03) | E 调 shutdown | `client.ts` + `DashboardPage` Dashboard 真实 API + npm build ✅ |

### 关于 A 和 C 的当前 work

两位成员是由旧 E 在 RC-03 阶段通过 `team_reactivate` 唤醒的：
- A 被派去修复 67 个 SAR 回归测试（数据依赖问题，非代码问题）
- C 被派去增强 Evidence/Summary 真实化

截至本 handoff 生成时，A 和 C 均已发出 `[System: New team message]` 通知，**尚未读取**。新 E 启动后的第一件事应该是读取 A 和 C 的汇报。

---

## 7. 已知风险

| 风险 | 等级 | 说明 |
|------|:----:|------|
| A 共享 worktree 可能已丢失 | P1 | A 是旧 A（不是被 shutdown 后重建的 rc03），worktree 路径仍存在。但 10+ 小时 session 已过期，re-activate 后 session 是否仍有效未知 |
| C 共享 worktree 可能已丢失 | P1 | 同上 |
| B 和 D 成果不可恢复 | P2 | 旧 E 错误 shutdown 了 B rc03 和 D rc03，它们的 commit 在 preserved 分支上但无法 merge（旧 baseline 冲突）。需要手动 cherry-pick 或重写 |
| 67 SAR 回归测试 | P2 | A 的数据依赖问题，不是纯代码修复 |
| Candidate GeoJSON 仍为 Mock | P3 | 需要 A 的 SAR 几何数据 |
| 比赛适配未开始 | P3 | Dataset Registry/License Matrix/Split Policy 均未做 |
| RC-01 审查结论 CHANGES_REQUIRED | P1 | PR #20 待修复后重新审查 |

---

## 8. 下一步优先级

**[事实来源: 用户已确认方向，具体顺序由新 E 决定]**

1. **P0** 读取 A 和 C 的 team_results（两者均已发送消息）
2. **P0** 关闭 A 和 C 完成后，`team_merge` 或 cherry-pick 其成果
3. **P1** 重做 B 和 D 丢失的成果（runs 真实化 + Dashboard 真实 API）
4. **P1** 修复 RC-01 审查问题 → CHANGES_REQUIRED 清单
5. **P2** 完成 Runs/Artifacts 的真实化（用 Agent B，非 E 手工）
6. **P2** 完成 Dashboard 真实 API 接入（用 Agent D，非 E 手工）
7. **P3** P5 INT-01/02 集成测试
8. **P3** P6 RC-02/RC-03 发布候选
9. **待定** 比赛适配（Dataset Registry/License Matrix/Split Policy/Adapter）

---

## 9. 还原 Team 启动步骤

给新 AGENT_E 的详细启动流程：

### 第 1 步：进入项目根目录

```powershell
cd D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\integration
git checkout integration/g0-g1-contract-freeze
git pull origin integration/g0-g1-contract-freeze
```

### 第 2 步：验证 Git 状态

```powershell
git rev-parse --show-toplevel
git rev-parse --short HEAD    # 应 = f96a5eb
git status --short            # 应 = 只有 real_service.py dirty
```

### 第 3 步：读取治理文档

```
AGENTS.md
agents/sessions.yml
agents/项目经理_AGENT_E.md
docs/program/STATUS_BOARD.md
docs/program/MASTER_ROADMAP.md
docs/program/MULTI_SESSION_OPERATIONS.md
docs/program/DECISION_LOG.md
docs/program/CONTRACT_GAP_REGISTER.md
```

### 第 4 步：恢复 Team

```powershell
team_status  # 检查现有成员
```

如果 A（perception-agent-a）和 C（event-agent-c）仍是 `ready` 状态：
```powershell
team_results --from perception-agent-a  # 读 A 的汇报
team_results --from event-agent-c       # 读 C 的汇报
```

### 第 5 步：决定 B 和 D 重建

B 和 D 是 shutdown 状态不可 reactivate。新 E 需与用户讨论：
- 是重新 spawn B 和 D？
- 还是用不同名字（B-rc04/D-rc04）？

### 第 6 步：代理任务角色划分

| 代理 | 待完成工作 |
|:----:|-----------|
| A | SAR 回归修复 + Candidate GeoJSON |
| B (重建) | RunManifest 真实存储 + CI + preflight |
| C | Evidence/Summary 增强 + 合同扩展 |
| D (重建) | Dashboard 真实 API + Candidate 前端路由 |

---

## 10. 关键用户指令归档

**[事实来源: 用户已确认]**

### 当前唯一有效的用户指令

> **m00824**: "把这个做完，spawnsub session开始做，team_reactivate之前的subsession，平行并行做"

### 已被覆盖的历史指令

| 用户指令 | 状态 | 被谁覆盖 |
|---------|:----:|---------|
| m00001 E 启动 Prompt | ✅ 已完成 | m00824 |
| GOV-05A 13 项修正 | ✅ 已完成 | PR #16 merged |
| "直接跑到 Phase 6" | ✅ P1-P4 完成 | RC-01 CHANGES_REQUIRED |

### 用户长期确认的规则

- 不重复 spawn / 不 shutdown / 用 team_reactivate
- 正式 Team 不 cleanup
- Worktree 和 Branch 长期复用
- Agent 成果走 PR 合入
- E 不手工复制 Agent 文件

---

## 11. 禁止操作

**[事实来源: 用户已确认]**

新 AGENT_E **不得**：

1. **不得** 自动 merge 任何分支到 develop/main
2. **不得** 调用 `team_cleanup` 清除正式 Team
3. **不得** `team_shutdown` 正式成员（除非用户明确要求）
4. **不得** 手工在 integration 上修改 Agent 所有权文件（见 AGENTS.md §7 代码所有权表）
5. **不得** 在未与用户确认前继续 P5/P6 或比赛适配
6. **不得** 使用 `general` / `Sisyphus` / `ultraworker` agent 类型
7. **不得** 在未读取 A 和 C 的汇报前进行任何开发

---

## 12. 事实来源标注

| 标记 | 含义 |
|:----:|------|
| **Git 已确认** | 信息源自 git log/diff/status 输出 |
| **文件已确认** | 信息源自文件读取 |
| **用户已确认** | 信息源自用户明确说出的指令或规则 |
| **旧 E 推断** | 仅为旧 E 的判断，新 E 应验证 |

---

*交接完毕。新 AGENT_E 按 §9 启动步骤开始，先读 A 和 C 的汇报，再向用户报告状态。*
