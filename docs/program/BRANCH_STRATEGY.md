# 山水智鉴 — 分支策略

> **版本**: v1 (GOV-02)
> 基于 `integration/g0-g1-contract-freeze` 的 clean branch 集成模型。

---

## 分支模型

```
main (发布标签, 只读)
  ↑
develop (日常集成分支)
  ↑
integration/g0-g1-contract-freeze (G0-G1 集成门禁基线)
  ↑
feature/agent-*-* (各 Agent 工作分支, 从 integration 创建)
```

---

## 分支类型

| 分支类型 | 命名模式 | 创建自 | 合并至 | 说明 |
|----------|----------|--------|--------|------|
| 发布 | `main` | `develop` | - | 只读，仅打标签 |
| 开发集成 | `develop` | - | - | 日常开发基线 |
| 门禁集成 | `integration/g*-g*-*` | `develop` | `develop` | 阶段集成门禁 |
| Agent 功能 | `feature/agent-*-*` | `integration/g0-g1-contract-freeze` | `integration/g0-g1-contract-freeze` | 单个 Agent 工作分支 |
| 修复 | `fix/agent-*-*` | `integration/g0-g1-contract-freeze` | `integration/g0-g1-contract-freeze` | Bug 修复 |
| 调研 | `spike/*` | 任意 | - | 技术调研，不合并 |

---

## Agent 功能分支规范

### 创建

```bash
git fetch origin
git switch --detach origin/integration/g0-g1-contract-freeze
git switch -c feature/agent-{a|b|c|d|e}-{work-package}
git push -u origin feature/agent-{a|b|c|d|e}-{work-package}
```

### Clean Branch 要求

- 只包含该 Agent 允许修改目录的文件
- 不得包含跨 Agent 领域的文件（除非经过正式合同变更流程）
- 必须从最新 `integration/g0-g1-contract-freeze` 创建

### 禁止

- ❌ 从旧 Agent 分支创建新分支
- ❌ 从 `main` 创建开发分支
- ❌ 从 `develop` 直接创建功能分支
- ❌ 一条分支包含多个 Agent 的工作

---

## 合并流程

```
feature/agent-b-g0.3-reliability-clean
    → PR → code review → Gate 检查
    → merge to integration/g0-g1-contract-freeze
    → 全量测试
    → 下一个 Agent 开始...

feature/agent-a-g0.3-candidate-clean
    → PR → code review → Gate 检查
    → merge to integration/g0-g1-contract-freeze
    → 全量测试
    → 下一个 Agent 开始...
```

### Merge 命令

```bash
# 在 integration 分支上
git merge --no-ff feature/agent-*-*
```

### 禁止

- ❌ octopus merge
- ❌ force push develop/main
- ❌ 重写 develop 历史
- ❌ 一次性合入多个 Agent

---

## 标签规范

```
v<major>.<minor>.<patch>
```

例如：
- `v0.1.0` — 首次集成发布
- `v0.1.1` — Bug 修复
- `v0.2.0` — 视频感知加入

---

## 阶段性分支升级

当 `integration/g*-g*-*` 阶段完成后：

```bash
# integration → develop
git checkout develop
git merge --no-ff integration/g0-g1-contract-freeze
git push origin develop
```

当 `develop` 稳定后：

```bash
# develop → main
git checkout main
git merge --no-ff develop
git tag v0.1.0
git push origin main --tags
```
