# 山水智鉴 V0 — 用户流程

> 版本: v0.1
> 更新: 2026-07-26

---

## 1. 核心研判流程

```
开始
  │
  ├─ 打开工作台
  │   ├─ 默认加载 persistent + uncertain Candidate
  │   └─ 地图自动定位到研究区
  │
  ├─ 浏览 Candidate 队列
  │   ├─ 滚动列表浏览
  │   ├─ 筛选（change_type / AOI / Run / 时间）
  │   ├─ 排序（score / area / occurrence_count）
  │   ├─ 分页（游标分页）
  │   └─ 切换 transient 显示
  │
  ├─ 选中 Candidate
  │   ├─ 地图定位至 Candidate 位置
  │   ├─ 突出显示代表几何
  │   └─ 右侧加载详情
  │
  ├─ 核验证据
  │   ├─ 查看 Evidence 列表
  │   ├─ 切换影像图层（SAR / 中位数 / NDWI）
  │   ├─ 切换对比模式（透明度 / 左右分屏）
  │   ├─ 调整图层透明度
  │   └─ 查看图例
  │
  ├─ 做出 Review 决策
  │   ├─ confirm  → 自动创建 Event
  │   ├─ reject   → 需填写原因
  │   ├─ reclassify → 选择新类别
  │   └─ needs_more_evidence → 记录需求
  │
  ├─ Review 后
  │   ├─ 保留地图位置
  │   ├─ 刷新 Candidate 状态
  │   ├─ Event 更新
  │   └─ Replay 记录
  │
  └─ 冲突处理
      ├─ 保留用户评论
      └─ 提供重新加载最新版本按钮
```

## 2. 事件中心流程

```
事件中心
  ├─ 查看 Event 列表
  │   ├─ 筛选（状态 / 类别 / 时间）
  │   └─ 搜索
  ├─ 点击 Event
  │   ├─ 查看基本信息
  │   ├─ 查看版本历史
  │   ├─ 查看 Candidate 来源
  │   ├─ 查看 Evidence Bundle
  │   ├─ 查看 Review Decision
  │   ├─ 查看 Replay
  │   └─ 地图定位
  └─ 返回列表
```

## 3. 运行追溯流程

```
运行记录
  ├─ 查看 Run 列表
  │   ├─ 筛选（状态 / 时间）
  │   └─ 搜索
  ├─ 点击 Run
  │   ├─ 查看运行参数
  │   ├─ Candidate → Observation → Asset → Artifact 链路
  │   ├─ 产物 SHA256 校验
  │   └─ 查看 TileJSON
  └─ 返回列表
```

## 4. Replay 浏览流程

```
Replay
  ├─ 定位到 Event
  ├─ 查看 Replay 条目列表
  ├─ 按时间线顺序浏览
  │   ├─ Candidate 创建
  │   ├─ Evidence 收集
  │   ├─ Review 决策
  │   └─ Event 状态变更
  └─ 回放操作细节
```
