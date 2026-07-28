# 山水智鉴 V0 — 产品需求文档

> 版本: v0.1
> 更新: 2026-07-26
> 负责人: Agent D

---

## 1. 产品目标

山水智鉴 V0 定位为面向河湖异常研判人员的多源水域异常感知与证据研判工作台，将遥感和后续视频模型输出转化为可定位、可解释、可审核、可追溯的异常候选。

**核心价值主张：**
- 统一多源异常结果的接入与展示
- 提供可解释的证据编排与核验流程
- 保证操作全链路可追溯（Replay）

---

## 2. 用户角色

### 主要用户
| 角色 | 职责 | 使用场景 |
|------|------|----------|
| 河湖异常研判人员 | 日常核验 Candidate、审核证据、做出 Review 决策 | 工作台首页日常操作 |

### 兼顾用户
| 角色 | 使用场景 |
|------|----------|
| 比赛演示人员 | 展示产品完整闭环 |
| 算法研发人员 | 追溯 Run 输出、查看 Candidate 评分构成 |
| 系统管理员 | 系统设置维护 |

---

## 3. 用户问题

| 问题 | 产品回答 |
|------|----------|
| 遥感模型的 Candidate 无法对应到具体地理位置 | 地图定位 + 矢量叠加 |
| 无法确认 Candidate 是否有足够证据 | Evidence 面板集中展示所有证据 |
| 人工核验后结果未保留 | Review 版本化 + Replay 追溯 |
| 操作链路不透明 | 全操作 Replay 记录 |
| 异常类别无法灵活调整 | Reclassify 支持 |

---

## 4. 核心闭环

```
Candidate
→ 地图定位
→ 影像与证据核验
→ 人工研判
→ Review 决策（confirm / reject / reclassify / needs_more_evidence）
→ Event 状态更新
→ 操作回放（Replay）
→ Run 追溯
```

---

## 5. 页面结构

### 一级导航
| 导航项 | 路由 | 说明 |
|--------|------|------|
| 研判工作台 | `/` | 三栏布局首页 |
| 事件中心 | `/events` | Event 列表与管理 |
| 运行记录 | `/runs` | Run 执行记录追溯 |
| 系统设置 | `/settings` | 系统配置 |

### 研判工作台布局
```
┌────────────────────────────────────────────────────────┐
│  Header / Navigation                                    │
├────────────┬───────────────────────────┬────────────────┤
│ ~320px     │     Flex                  │ ~400px         │
│            │                           │                │
│ Candidate  │   地图 / 影像区域         │ Candidate      │
│ 队列       │                           │ 详情           │
│            │   - 历史 SAR              │ + Evidence     │
│ 筛选       │   - 当前 SAR              │ + Review       │
│ 排序       │   - 当前中位数            │  表单          │
│ 分页       │   - water gain/loss       │                │
│            │   - SAR anomaly           │                │
│            │   - Candidate geometry    │                │
│            │   - Event geometry        │                │
│            │                           │                │
│            │ 图层工具栏 + 对比面板     │                │
└────────────┴───────────────────────────┴────────────────┘
```

---

## 6. 功能范围

### V0 包含
- [x] Candidate 列表（persistent / uncertain 默认，transient 可选）
- [x] Candidate 筛选（change_type / AOI / Run / 时间 / bbox / 排序 / 游标分页）
- [x] Candidate 详情（完整字段 + ScoreBreakdown）
- [x] 地图定位与影像叠加
- [x] 图层切换（可见性 / 透明度 / 图例）
- [x] 对比模式（透明度叠加 / 左右分屏）
- [x] Evidence 多模态展示
- [x] Review 四类动作 + 冲突处理
- [x] Event 中心（版本历史）
- [x] Run 中心（产物追溯）
- [x] Replay 全流程回放
- [x] URL 状态恢复
- [x] Mock / Real API 双模式
- [x] Design Tokens 主题系统

### V0 不包含
- [ ] WorkOrder
- [ ] 视频联动
- [ ] Swipe 对比模式
- [ ] 时间动画
- [ ] AOI 绘制
- [ ] 测距测面积
- [ ] 正式登录
- [ ] 权限管理
- [ ] WebSocket 实时推送
- [ ] 最终品牌视觉定稿

---

## 7. 非功能要求

| 要求 | 标准 |
|------|------|
| Mock 首屏加载 | < 3 秒 |
| Candidate 选中到地图定位 | < 500ms |
| 图层切换 | 不重建 Map 实例 |
| 最小分辨率 | 1280px 不破版 |
| 请求状态 | 全部有 Loading |
| 错误处理 | 全部有 Error State |
| 空数据处理 | 全部有 Empty State |
| 状态表达 | 不只依赖颜色 |
| 数据隔离 | 前端不访问数据库 |
| 文件隔离 | 前端不读取算法目录 |
| 模式切换 | Mock 和 Real 可配置切换 |

---

## 8. 禁止范围

- 禁止显示风险概率、准确率、严重度、违法确认、污染确认
- 禁止 WorkOrder
- 禁止正式登录（所有写操作预留 actor_ref）
- 禁止前端直接访问 SQLite 或 output 目录
- 禁止 Redux 存储全部后端数据
- 禁止 Jinja2 扩建正式页面
- 禁止微前端
- 禁止 React-admin 承担核心地图工作台
- 禁止业务组件直接裸 fetch

---

## 9. 验收标准

| ID | 标准 | 验证方式 |
|----|------|----------|
| AC01 | 工作台三栏布局正确 | Playwright 截图对比 |
| AC02 | Candidate 列表显示 | Playwright 断言 |
| AC03 | Score 显示为"本次运行排序分" | 前端检查文案 |
| AC04 | 地图定位 < 500ms | 测量 |
| AC05 | Transient 默认隐藏 | Playwright 断言 |
| AC06 | Transient 可手动开启 | Playwright 操作 |
| AC07 | Review 四类动作均可用 | Playwright 操作 + API 验证 |
| AC08 | Conflict 提示保留用户评论 | Playwright 断言 |
| AC09 | URL 刷新恢复状态 | Playwright 操作 |
| AC10 | Mock 模式首屏 < 3s | 测量 |
| AC11 | 1280px 不破版 | Viewport 测试 |
| AC12 | 所有请求有 Loading | 断言 loading spinner |
| AC13 | API Error 显示 Error State | Mock 500 测试 |
| AC14 | 空数据 Empty State | Mock 空列表测试 |
| AC15 | Replay 全流程可追溯 | Playwright 回放查看 |

---

## 10. 比赛开放后待验证项

详见 [COMPETITION_DISCOVERY_CHECKLIST.md](./COMPETITION_DISCOVERY_CHECKLIST.md)
