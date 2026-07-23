# GeoAgent 项目记忆

> 最后更新: 2026-07-23（经用户审查修正）

## 项目身份
- 山水智鉴 V0 — 多模型适配、证据编排与人工核验中间件
- 双赛并行：IAIC（算法赛） + 智慧城市大赛（产品赛）

## 当前阶段
**工程骨架、数据下载、光学单期水体提取、Schema、API和页面壳已完成**
- 双时相变化检测未闭合（S2 T2 云覆盖）
- SAR 分支未开发（已下载但未进 Pipeline）
- 空间基准用错（EPSG:4526 → 应改为 EPSG:4545）

## 已确认的技术问题（待修复）
| 问题 | 影响 | 修复方向 |
|------|------|---------|
| EPSG:4526 朝天门偏差 7.4° | 所有面积/距离/叠加错误 | 改为 EPSG:4545 |
| skimage.resize 替换地理对齐 | CRS/transform 不连续 | 改为 rasterio.warp.reproject |
| T2 无数据输出为"无变化" | 语义错误 | 增加三态区分 |
| S1 未进入处理链 | 双传感器方案未执行 | 新增 SAR 分支 |
| 分区 Otsu 未验证 | 日志不透明 | 增加诊断输出 |

## 链式架构
```
GEE数据下载 → InputAdapter → Preprocessor(CRS待修) → FeatureExtractor
→ ModelClient V0(光学) + [待建:SAR分支]
→ ChangeDetector(待S1接入) → Polygonizer → DetectionResult
→ COG→TiTiler 地图服务(待验证)
→ EvidenceBundle → 人工核验 → SQLite → Replay(待持久化)
```

## 技术栈 V0
Python 3.11, Rasterio, numpy, rio-cogeo, TiTiler, FastAPI, Pydantic v2, pytest
DEM源: COPERNICUS/DEM/GLO30 (ImageCollection, 需 .mosaic())
正确CRS: EPSG:4545 (CGCS2000 / CM 108°E)

## 诚实标注规则
- ✅ 真实遥感数据
- ✅ 算法候选（非政府认定违法）
- ❌ 不称"已完成全链路"——SAR 分支、空间基准、持久化均未通过
