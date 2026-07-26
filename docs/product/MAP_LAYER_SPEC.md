# 山水智鉴 V0 — 地图图层规范

> 版本: v0.1
> 更新: 2026-07-26

---

## 1. WorkbenchLayer 定义

```typescript
interface WorkbenchLayer {
  id: string;
  title: string;
  group: 'basemap' | 'sar' | 'change' | 'mask' | 'vector';
  layerType: 'raster' | 'vector' | 'mask' | 'candidate' | 'event';
  sourceType: 'tilejson' | 'geojson' | 'cog';
  sourceUrl: string;
  visibleByDefault: boolean;
  opacity: number;           // 0-1
  zIndex: number;
  legend?: LayerLegend;
  temporalExtent?: [string, string];  // ISO dates
  bounds?: [number, number, number, number];  // [west, south, east, north]
  metadata?: Record<string, any>;
}

interface LayerLegend {
  type: 'gradient' | 'categorical' | 'single';
  items: LegendItem[];
}

interface LegendItem {
  label: string;
  color: string;
  value?: number | string;
}
```

---

## 2. 默认图层清单

| ID | Title | Group | Type | Visible |
|----|-------|-------|------|---------|
| `sentinel2_recent` | 最新 Sentinel-2 | basemap | raster | true |
| `sentinel2_median` | 中位数参考 | basemap | raster | false |
| `sar_recent` | 当前 SAR | sar | raster | false |
| `sar_historical` | 历史 SAR | sar | raster | false |
| `water_gain` | 水面增加 | change | raster | true |
| `water_loss` | 水面减少 | change | raster | true |
| `sar_anomaly` | SAR 异常 | change | raster | false |
| `persistent_mask` | 持久性掩膜 | mask | mask | false |
| `transient_mask` | 瞬态掩膜 | mask | mask | false |
| `candidates` | 异常候选 | vector | candidate | true |
| `events` | 异常事件 | vector | event | true |

---

## 3. Layer Registry 设计

```typescript
class LayerRegistry {
  private layers: Map<string, WorkbenchLayer>;

  register(layer: WorkbenchLayer): void;
  deregister(id: string): void;
  get(id: string): WorkbenchLayer | undefined;
  getAll(): WorkbenchLayer[];
  getByGroup(group: string): WorkbenchLayer[];
  getVisible(): WorkbenchLayer[];
  setVisible(id: string, visible: boolean): void;
  setOpacity(id: string, opacity: number): void;
}
```

核心原则：新增图层不得要求修改 GovernanceMap 核心实现。

---

## 4. 地图能力矩阵

| 能力 | V0 | 备注 |
|------|----|------|
| 底图切换 | ✓ | — |
| 图层可见性 | ✓ | 每个图层独立控制 |
| 图层透明度 | ✓ | 0-100% 滑动调节 |
| 图例显示 | ✓ | Gradient / Categorical |
| 图层分组 | ✓ | Basemap / SAR / Change / Mask / Vector |
| 透明度叠加对比 | ✓ | 两层叠合 |
| 左右分屏对比 | ✓ | 独立控制左右图层 |
| 候选定位 | ✓ | 选中后 flyTo |
| 事件定位 | ✓ | 选中后 flyTo |
| Feature Popup | ✓ | 点击显示基本信息 |
| Loading 状态 | ✓ | 瓦片加载中提示 |
| Error 状态 | ✓ | 图层加载失败提示 |
| 空状态 | ✓ | 无数据提示 |
| Swipe 对比 | ✗ | V1 考虑 |
| 时间轴动画 | ✗ | V1 考虑 |
| AOI 绘制 | ✗ | V1 考虑 |
| 测距测面积 | ✗ | V1 考虑 |
