# GeoCode → OpenChamber 迁移 SOP

> 版本：v1.0  
> 日期：2026-07-28  
> 适用项目：山水智鉴  
> 目标：保留 GeoCode 的 GIS 能力和 Ensemble 多 Agent 控制面，在 OpenChamber 中获得更开放的 UI、原生 worktree、Git/PR 与 Session 管理能力。  
> 原则：先复制验证，后切换；GeoCode 保留为可回滚的只读环境。

## 1. 当前事实基线

### 1.1 GeoCode 当前配置

- 正式配置目录：`C:\Users\WangChi\.claude\geocode`
- 当前唯一启用插件：`@hueyexe/opencode-ensemble`
- Ensemble 安装版本：`0.15.2`（本机已有自定义修复）
- `mergeOnCleanup=false`
- ACP 压缩已停用，不进入迁移范围
- Oh My OpenAgent 虽仍可能存在于 `node_modules`，但不在当前 `plugin` 列表中，不进入首轮迁移
- 全局 GIS 指令：`C:\Users\WangChi\.claude\geocode\AGENTS.md`
- Skill 路径：`C:\Users\WangChi\.claude\skills`
- GEE 凭据：`C:\Users\WangChi\.config\earthengine\credentials`
- GDAL 命令已在 PATH 中可见，例如：`D:\Q Gis\bin\gdalinfo.exe`
- QGIS Desktop 可执行程序存在：`D:\Q Gis\bin\qgis-ltr-bin.exe`

### 1.2 当前多 Agent 架构

```text
用户（最终决策人）
└── 项目经理_AGENT_E（顶层 Session / Ensemble Lead）
    ├── 感知算法_AGENT_A（child Session + 独立 worktree）
    ├── 工程可靠性_AGENT_B（child Session + 独立 worktree）
    ├── 事件治理_AGENT_C（child Session + 独立 worktree）
    └── 产品工作台_AGENT_D（child Session + 独立 worktree）
```

Agent E 通过 `team_message`、`team_status`、`team_results`、`team_view`、
`team_reactivate` 等工具管理 A/B/C/D。

> 工具准确名称以当前插件实际暴露为准。本机源码中已确认存在的是
> `team_reactivate`；若 UI 显示 `team_activate`，验收时必须记录二者的真实映射，
> 不得只凭口头名称判断。

### 1.3 迁移后目标

```text
OpenChamber（开放 GUI / Session 与 Git 操作界面）
└── OpenCode Server（独立配置与数据目录）
    └── 项目经理_AGENT_E
        └── Ensemble persistent team
            ├── A / 独立 Session / 独立 worktree / 独立 branch
            ├── B / 独立 Session / 独立 worktree / 独立 branch
            ├── C / 独立 Session / 独立 worktree / 独立 branch
            └── D / 独立 Session / 独立 worktree / 独立 branch
```

## 2. 什么能迁移，什么不能直接迁移

| 内容 | 迁移方式 | 结论 |
|---|---|---|
| `AGENTS.md` 地理智能体指令 | 复制到新 OpenCode profile，并在 `instructions` 显式引用 | 可完整迁移 |
| GEE/GDAL/QGIS Skills | 保留原 Skill 目录，只读引用；稳定后再复制 | 可完整迁移 |
| GEE OAuth 凭据 | 使用系统现有凭据，不复制进仓库 | 可复用 |
| GDAL/QGIS 程序 | 依赖 Windows PATH 和本机安装 | 可复用 |
| Ensemble 插件与自定义修复 | 从已验证插件目录复制到独立 profile | 可迁移，必须回归测试 |
| `team_reactivate` | 插件能力，不依赖 GeoCode UI | 可迁移，需实测 |
| 项目 `AGENTS.md`、Agent Prompts、Status Board | 保留在 Git 仓库 | 自动可用 |
| Git branches/worktrees | 由 Git 与 OpenCode/Ensemble 管理 | 可复用 |
| GeoCode `geocode.json` | OpenChamber/OpenCode 不保证解析该专有文件 | 不直接迁移 |
| GeoCode 左侧栏布局和客户端状态 | 属于 GeoCode UI 数据 | 不迁移 |
| GeoCode 旧聊天记录 | 存储格式和索引未冻结 | 首轮不迁移，保留 GeoCode 查询 |
| ACP 压缩 | 已停用 | 不迁移 |
| Oh My OpenAgent | 当前不是正式插件 | 首轮不迁移 |

## 3. GIS 能力保留原则

GeoCode 的 GIS 能力不是单一组件，必须同时保留四层：

1. **身份与方法层**：`AGENTS.md`
2. **工作流层**：GEE、QGIS、遥感等 Skills
3. **工具层**：Python、GDAL、QGIS、PyQGIS、QGIS MCP
4. **凭据与网络层**：GEE OAuth、代理、环境变量

迁移后若只看到模型能聊天，不能据此认定 GIS 能力迁移完成。必须通过第 8 节的
真实 GIS 验收。

当前 `geocode.json` 的 `gee.python`、`gee.project`、`gdal`、
`qgis.python`、`qgis.prefix` 均为空，因此现有 GIS 能力主要来自系统环境、
凭据、Skills 和 `AGENTS.md`，并非依赖该文件中的有效路径。

## 4. 目录设计

创建独立迁移环境，不覆盖 GeoCode：

```text
D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber\
├── config\                 # OpenCode 配置、AGENTS、插件
├── data\                   # OpenCode Session 数据
├── openchamber-data\       # OpenChamber UI 数据
├── ensemble\               # Ensemble DB 与备份
├── logs\
├── backup\
└── scripts\
```

建议变量：

```powershell
$env:OPENCODE_CONFIG_DIR =
  "D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber\config"

$env:OPENCODE_DATA_DIR =
  "D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber\data"

$env:OPENCHAMBER_DATA_DIR =
  "D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber\openchamber-data"

$env:OPENCODE_ENSEMBLE_DB =
  "D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber\ensemble\ensemble.db"
```

> **阻断项**：本机当前 Ensemble `src/db.ts` 的 `getDbPath()` 仍按
> `%HOME%`/`%USERPROFILE%\.config\opencode\ensemble.db` 计算数据库路径，
> 尚未读取 `OPENCODE_ENSEMBLE_DB`。因此上面的变量是目标合同，不是当前已生效
> 的事实。Phase 1 前必须先为插件补充并测试该路径覆盖；否则 GeoCode 与
> OpenChamber 不得同时运行 Ensemble。

首轮不要将新环境直接指向：

- `C:\Users\WangChi\AppData\Roaming\ai.geocode.desktop`
- GeoCode 正在使用的 Session 数据
- GeoCode 正在使用的 Ensemble DB

避免两个客户端同时写同一个 SQLite 或 Session 存储。

### 4.1 启动脚本要求

必须从设置上述环境变量的**同一个 PowerShell 进程**启动 OpenChamber，
不能设置变量后再从开始菜单单独打开。

```powershell
$MigrationRoot = "D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber"
$OpenChamberExe = "<从 OpenChamber 快捷方式属性取得的真实 exe 路径>"

$env:OPENCODE_CONFIG_DIR = Join-Path $MigrationRoot "config"
$env:OPENCODE_DATA_DIR = Join-Path $MigrationRoot "data"
$env:OPENCHAMBER_DATA_DIR = Join-Path $MigrationRoot "openchamber-data"
$env:OPENCODE_ENSEMBLE_DB = Join-Path $MigrationRoot "ensemble\ensemble.db"

if (-not (Test-Path -LiteralPath $OpenChamberExe)) {
  throw "OpenChamber executable not found: $OpenChamberExe"
}
Start-Process -FilePath $OpenChamberExe
```

环境隔离不能只靠 Agent 回显。启动后必须新建一个测试 Session，再以文件系统
时间戳、实际数据库路径和 OpenChamber diagnostics 证明写入发生在迁移目录。

## 5. 分阶段迁移

### Phase 0｜冻结与备份

操作：

1. 关闭 GeoCode。
2. 确认没有 GeoCode/OpenCode/Ensemble 后台进程继续写数据库。
3. 记录以下版本和校验值：
   - GeoCode 版本
   - OpenChamber 版本
   - OpenCode 版本
   - Ensemble 版本与插件目录 SHA256
   - `opencode.json` SHA256
   - `AGENTS.md` SHA256
   - `ensemble.db` SHA256
4. 复制备份：
   - `C:\Users\WangChi\.claude\geocode`
   - `C:\Users\WangChi\.config\opencode\ensemble.db*`
   - 项目 `agents/`、`docs/program/`
5. 导出 `git worktree list --porcelain` 和 `git branch -avv`。
6. 检查 Ensemble `getDbPath()` 是否支持 `OPENCODE_ENSEMBLE_DB`：
   - 支持：记录源码行和测试结果；
   - 不支持：先在插件独立修复分支中加入显式路径覆盖，再构建和测试；
   - 禁止用修改全局 `HOME`/`USERPROFILE` 的方式绕过，因为这会同时改变
     Git、SSH、GEE 凭据和其他用户级路径。
Gate：

```text
BACKUP_VERIFIED
ENSEMBLE_DB_PATH_OVERRIDE_SUPPORTED
```

失败则停止，不进入 Phase 1。

### Phase 1｜建立 OpenChamber 独立 Profile

只复制以下内容到新 `config\`：

- `opencode.json`
- `AGENTS.md`
- `ensemble.json`
- `package.json`
- `package-lock.json`
- 已验证的 `@hueyexe/opencode-ensemble` 插件

修改要求：

- 将已验证的自定义 Ensemble 构建作为**本地插件副本**放入新 profile，
  并让 `opencode.json` 显式加载该本地入口；不要只填写 npm 包名，否则
  OpenCode 启动时可能重新安装公开版并覆盖本机的 lifecycle、
  `team_reactivate` 和数据库路径修复
- 首轮只加载这一份 Ensemble，禁止同时加载同名 npm 版与本地版
- 不启用 ACP
- 不启用 Oh My OpenAgent
- `instructions` 改为新 profile 中 `AGENTS.md` 的绝对路径
- `skills.paths` 首轮继续引用 `C:\Users\WangChi\.claude\skills`
- `mergeOnCleanup` 保持 `false`
- 模型必须显式指定，避免 child Session 回退到其他默认模型
- 使用专用 PowerShell 启动脚本设置环境变量后启动 OpenChamber；不要直接从
  Windows 开始菜单启动并假设变量会自动继承
- 启动后既要由 Agent 回显变量值，也要核对真实落盘路径
- 记录实际加载的插件绝对路径和构建 SHA256，防止误加载缓存中的公开版

完成最小 profile 和本地插件安装后，用迁移启动脚本启动一次 OpenChamber，
创建测试 Session 后关闭：

- 检查 `OPENCHAMBER_DATA_DIR` 下出现新的 UI 数据；
- 检查 `OPENCODE_DATA_DIR` 下出现新的 Session 数据；
- 检查实际打开的 Ensemble DB 等于 `OPENCODE_ENSEMBLE_DB`；
- 任一数据仍落入 GeoCode/AppData 原目录，立即判定隔离失败。

Gate：

```text
OPENCHAMBER_PROFILE_BOOTED
MIGRATION_DATA_PATHS_VERIFIED
```

### Phase 2｜基础能力烟雾测试

在 OpenChamber 新建普通 Session，执行只读测试：

1. 能读取项目 `AGENTS.md`
2. 能识别全局 GeoAgent 指令
3. 能列出 GIS Skills
4. `gdalinfo --version` 成功
5. Python 能导入项目实际需要的 GIS 包
6. GEE 凭据文件存在，但不得输出凭据内容
7. QGIS MCP 未连接时能明确报告“未连接”，不能伪造成功
8. Git 仓库、branch、worktree 可正确识别

Gate：

```text
GIS_RUNTIME_SMOKE_PASSED
```

### Phase 3｜Ensemble 控制面迁移

在一个独立、可丢弃的测试 Git 项目中创建临时 Agent E Session。不得在山水智鉴
正式 integration 项目内创建临时团队。

1. 确认存在：
   - `team_create`
   - `team_spawn`
   - `team_message`
   - `team_status`
   - `team_results`
   - `team_view`
   - `team_reconcile`
   - `team_reactivate`
   - `team_shutdown`
2. 创建临时团队，`persistent=true`。
   - 创建后直接查询/审计 Ensemble DB，确认该团队 `persistent=1`；
   - 当前本机 `executeTeamCreate` 已包含 `INSERT ... persistent`，迁移副本
     仍必须用运行时数据证明该字段真正写入。
3. 创建一个只读成员：
   - `worktree=false`
   - 显式模型
4. 验证 message → result → view → reactivate。
5. 保存证据后关闭成员，并只对这个临时测试团队执行 cleanup。
6. 确认临时团队不再是 active，测试项目中没有遗留可写 worktree。
7. 不对山水智鉴正式团队执行 cleanup。

Gate：

```text
ENSEMBLE_CONTROL_PLANE_PASSED
```

### Phase 4｜Worktree 与 Branch 隔离测试

使用一次性测试仓库或一次性测试分支，创建两个可写成员：

- 两个成员均 `worktree=true`
- 基于相同 integration commit
- 各自创建不同文件
- 各自提交到不同 branch

必须验证：

- worktree 绝对路径不同
- branch 不同
- `git status` 互不影响
- 一个成员的未提交文件在另一个成员中不可见
- 不发生自动 merge
- cleanup 不修改 integration/develop/main

#### 禁止双重 worktree

同一个 A/B/C/D 成员只能选择一种创建方式：

```text
方式 1：OpenChamber 原生 Worktree Session
方式 2：Ensemble team_spawn(worktree=true)
```

山水智鉴正式团队采用方式 2。不得先在 OpenChamber 创建一个 worktree
Session，再让该 Session 内的 Ensemble 为同一成员创建第二层 worktree。

Gate：

```text
WORKTREE_ISOLATION_PASSED
```

### Phase 5｜真实 A/B/C/D 团队重建

正式团队必须从已确认的 integration commit 创建。

`team_spawn` 不能直接指定 base commit、worktree 绝对路径或最终 branch 名称，
因此必须采用“先锚定 Lead，再逐个创建、逐个核验”的方式：

1. Agent E 所在项目目录必须是正式 integration worktree。
2. `git status --short --branch` 必须显示工作区干净。
3. `git rev-parse HEAD` 必须等于批准的 integration commit。
4. 每次只 spawn 一个成员并等待创建完成。
5. 立即进入该成员，记录插件实际生成的 worktree path、branch 和 HEAD。
6. 成员 HEAD 必须等于批准的 integration commit；不一致立即停止。
7. 只有 A 核验通过后才创建 B，依次创建 C、D。
8. 不对 Ensemble 自动生成的 worktree 路径或 branch 做事后手工改名。

每个成员记录：

| 字段 | 要求 |
|---|---|
| member name | 固定英文 ID |
| display role | 中文正式名称 |
| model | 显式指定 |
| worktree | `true` |
| base commit | 相同 integration commit |
| worktree path | 唯一绝对路径 |
| branch | 唯一分支 |
| allowed paths | 来自 Agent 角色文档 |
| forbidden paths | 来自 Agent 角色文档 |
| current work package | 只能有一个核心目标 |

创建后由 Agent E 写入：

- `agents/sessions.yml`
- `docs/program/STATUS_BOARD.md`
- `docs/handoff/AGENT_E_HANDOFF.md`

Gate：

```text
PERSISTENT_TEAM_REBUILT
```

### Phase 6｜持久化与重启验收

1. 保持团队成员处于可恢复状态。
2. 正常关闭 OpenChamber。
3. 重启 OpenChamber。
4. 打开 Agent E。
5. 由新的 Agent E 顶层 Session 使用正式团队的 `team_id` 或 `name`
   精确调用 `team_reconcile`，不得使用无参数的“恢复所有 persistent teams”：
   - 重新绑定当前 Lead Session；
   - 校验旧成员 Session；
   - 重注册成员；
   - 恢复未投递消息；
   - 返回 missing/reattached 成员清单。
6. `team_reconcile` 成功后，再激活/恢复原团队。
7. 检查 A/B/C/D：
   - Session 历史仍在
   - member 映射未重复
   - worktree 路径未变化
   - branch 未变化
   - 用户可进入 child Session 查看并直接对话
   - Agent E 可 `team_message`
   - completed/ready 成员可 `team_reactivate`
8. 重启后不得重新 spawn 同名 A/B/C/D，除非 `team_reconcile` 已明确确认
   原 Session 丢失且 Agent E 已记录恢复决策。

Gate：

```text
RESTART_RECOVERY_PASSED
```

### Phase 7｜真实 GIS 纵向验收

执行最小但真实的 GIS 验收：

1. **GDAL**
   - 先运行 `& "D:\Q Gis\bin\gdalinfo.exe" --version`
   - 对一个现有 GeoTIFF 运行同一绝对路径下的 `gdalinfo.exe`
   - 核对 CRS、尺寸、分辨率、NoData
2. **GEE**
   - 使用 `D:\py\Python3\python.exe`
   - 先验证 `import ee`
   - 只读查询一个公开数据集
   - 输出影像数量或元数据
   - 不启动大规模导出
3. **QGIS**
   - 从 `D:\Q Gis\bin\qgis-ltr-bin.exe` 启动 QGIS Desktop
   - 用 `D:\Q Gis\bin\python-qgis-ltr.bat` 验证 PyQGIS 环境
   - 按 `D:\研究生作业\人工智能实践比赛\山水智鉴_OpenChamber\config\skills\qgis-mcp\SKILL.md`
     启动 QGIS MCP Bridge
   - 验证 `127.0.0.1:9876` 已监听；未监听必须明确报告
   - 读取当前工程或创建空工程
   - 查询图层列表
   - 不修改正式 QGIS 工程
4. **Skill**
   - 触发 `gee-export-strategy`
   - 让 Agent 说明导出策略与质量 Gate
5. **项目能力**
   - 读取山水智鉴一个现有遥感产物
   - 给出不修改文件的 CRS/Bounds/NoData 审计
6. **环境继承**
   - 在 OpenChamber 内置终端重复检查 Python、GDAL 和代理变量
   - 结果必须与外部 PowerShell 一致；不一致则修启动脚本后重测

Gate：

```text
GEOSPATIAL_CAPABILITY_PASSED
```

### Phase 8｜切换与观察期

连续 3 个真实工作包使用 OpenChamber：

1. 一个只读审计任务
2. 一个单 Agent 小型编码任务
3. 一个 A/B/C/D 并行、E 汇总的集成任务

观察：

- Session 是否重复或丢失
- Agent E 是否能及时读取状态
- worktree 是否漂移
- child Session 是否可直接对话
- Git/PR/CI 是否清晰
- GIS 工具是否稳定
- token 与模型是否按显式配置执行

全部通过后：

```text
OPENCHAMBER_PRIMARY_READY
```

GeoCode 改为只读备用环境，至少保留 14 天。

## 6. Dashboard 与状态管理

OpenChamber 的 Session 列表和 worktree 视图不能替代项目治理看板。

正式状态源保持：

1. `docs/program/STATUS_BOARD.md`
2. `agents/sessions.yml`
3. `docs/handoff/AGENT_E_HANDOFF.md`
4. Git branch/commit/PR/CI
5. Ensemble `team_status`

Agent E 每轮必须把运行态同步成下面的统一表：

| Agent | Session | Worktree | Branch | Commit | Task | Status | Blocker | Next Gate |
|---|---|---|---|---|---|---|---|---|

OpenChamber 后续若提供成熟 Kanban，可作为展示层；上述 Git 内状态源仍保留。

## 7. Agent E 正式运行规则

Agent E 每次启动：

1. 读取项目 `AGENTS.md`
2. 读取 `agents/sessions.yml`
3. 读取 `STATUS_BOARD.md`
4. 若 OpenChamber/OpenCode 刚重启，先用正式 `team_id` 或 `name`
   精确执行 `team_reconcile`
5. 执行 `team_status`
6. 对照 Git worktree/branch/commit
7. 发现 completed/ready 成员需要新任务时使用 `team_reactivate`
8. 只有原 Session 丢失或处于不可恢复 error/shutdown 时才重新 `team_spawn`
9. 任何 merge 前执行对应 Gate
10. 不自动 merge integration/develop/main

用户可直接进入 A/B/C/D child Session 对话，但涉及任务范围变化时，应要求成员：

1. 将变化报告给 Agent E
2. 更新 Work Package 或 Handoff
3. 由 Agent E 刷新 Status Board

避免“用户直接改任务，但 E 不知道”的状态漂移。

## 8. 最小验收 Prompt

将下面内容发送给 OpenChamber 中的项目经理_AGENT_E：

```text
执行《GeoCode → OpenChamber 迁移验收》，只读优先，不修改正式代码，
不 Commit、不 Push、不 Merge、不 cleanup 正式团队。

请验证：

1. 当前 OPENCODE_CONFIG_DIR、OPENCODE_DATA_DIR、
   OPENCHAMBER_DATA_DIR、OPENCODE_ENSEMBLE_DB 是否全部指向
   山水智鉴_OpenChamber 独立目录；
   同时检查 Ensemble 实际打开的 SQLite 绝对路径，不能只检查环境变量；
2. 当前 plugin 列表是否只启用 @hueyexe/opencode-ensemble；
3. ACP 与 Oh My OpenAgent 是否未启用；
4. AGENTS.md 和 C:\Users\WangChi\.claude\skills 是否可发现；
5. team_create/spawn/message/status/results/view/reconcile/reactivate/shutdown 是否存在；
6. 在独立可丢弃的测试 Git 项目中创建一个 persistent 临时团队和一个
   worktree=false 的只读成员，显式使用 deepseek/deepseek-v4-flash；
   验证 DB 中 persistent=1；
7. 完成 message→results→view→reactivate；
8. 不调用 team_merge；保存证据后只 cleanup 临时测试团队，
   不调用正式团队 cleanup；
9. 运行 gdalinfo --version；
10. 检查 GEE 凭据文件存在但不输出内容；
11. 报告 QGIS MCP 是否已连接，未连接必须明确写未连接；
12. 输出实际工具名，确认是 team_reactivate 还是 team_activate。

最终只允许以下结论之一：

OPENCHAMBER_MIGRATION_SMOKE_PASSED
OPENCHAMBER_PROFILE_ISOLATION_FAILED
ENSEMBLE_PLUGIN_FAILED
GIS_RUNTIME_FAILED
CHANGES_REQUIRED
```

## 9. 回滚

出现以下任一情况立即回滚：

- OpenChamber 写入 GeoCode 正式数据目录
- Ensemble 成员绑定错误 branch/worktree
- 重启后成员重复创建
- child Session 无法直接进入或对话
- `team_reactivate` 失败且出现重复 Session
- GIS Skills 或凭据不可用
- 自动 merge 或 cleanup 影响受保护分支

回滚步骤：

1. 关闭 OpenChamber。
2. 确认 OpenChamber 管理的 OpenCode server、Ensemble 和相关子进程全部退出。
3. 等待日志写入完成，并确认迁移 SQLite 不再有写入且没有残留锁。
4. 不删除新环境，先将其重命名为带时间戳的故障现场。
5. 校验 GeoCode 原配置和原 Ensemble DB 哈希：
   - 若与 Phase 0 一致，直接原地启动，不执行覆盖；
   - 若确认被污染，先把污染后的文件复制到带时间戳的故障现场，
     再从 Phase 0 记录的明确备份路径恢复。
6. 恢复后重新计算哈希并与 Phase 0 对比。
7. 启动 GeoCode。
8. 核对原团队、Session、worktree、branch。
9. 在 `DECISION_LOG.md` 记录失败 Gate、日志和恢复结果。

回滚不得：

- 删除 Git branch
- 删除 worktree 中的未提交文件
- 在未确认污染、未保存故障现场时覆盖 GeoCode 原数据库
- 将测试环境数据库复制回正式环境

## 10. 最终完成定义

只有同时满足以下条件，才算迁移完成：

- OpenChamber 使用独立且可备份的 OpenCode profile
- GeoAgent 指令和 GIS Skills 正确加载
- GEE/GDAL/QGIS 最小真实验收通过
- Agent E 能控制 A/B/C/D
- 用户能直接进入 A/B/C/D Session 对话
- A/B/C/D 各自绑定唯一 worktree 和 branch
- `team_reactivate` 能在原 Session 上继续工作
- 重启后团队与历史可恢复
- 不自动 merge
- Status Board 与真实 Git/Session 状态一致
- GeoCode 保留可回滚副本

迁移完成状态：

```text
OPENCHAMBER_PRIMARY_READY
GEOCODE_READONLY_FALLBACK_READY
```

在达到这两个状态前，OpenChamber 只能标记为试运行环境。

## 11. 参考资料

- OpenChamber Worktree Sessions：<https://docs.openchamber.dev/worktrees/>
- OpenChamber 环境变量：<https://docs.openchamber.dev/zh-cn/environment/>
- OpenChamber Skills：<https://docs.openchamber.dev/zh-cn/skills/>
- OpenChamber 开源仓库：<https://github.com/openchamber/openchamber>
- OpenCode CLI 环境变量与 `OPENCODE_CONFIG_DIR`：
  <https://github.com/anomalyco/opencode/blob/dev/packages/web/src/content/docs/cli.mdx>
