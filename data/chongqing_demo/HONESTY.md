# 数据与结果诚实声明

> 山水智鉴 V0 — 重庆两江遥感异常研判原型

## 数据来源
| 数据 | 来源 | 说明 |
|------|------|------|
| Sentinel-2 L2A | GEE COPERNICUS/S2_SR_HARMONIZED | 真实卫星遥感数据 |
| Sentinel-1 GRD | GEE COPERNICUS/S1_GRD | 真实卫星雷达数据 |
| DEM | GEE COPERNICUS/DEM/GLO30 | 真实全球 DEM |
| 土地覆盖 | ESA WorldCover v200 | 2021 年静态产品 |
| 稳定水体 | JRC GSW v1.4 | 1984-2021 长期水体先验 |

## 结果说明
- 所有"异常候选"为**算法派生结果**，非政府认定的违法或"四乱"事件
- 置信度是**规则分数**（基于 NDWI 变化幅度和面积），非统计概率
- 水体范围变化可能包含**自然水位波动**，不直接等同于人类活动异常

## 角色说明
- 所有用户角色（demo_user、demo_dispatcher）为**演练角色**
- 核验、工单、处置流程为**产品流程验证**，非真实部门操作

## 版本
- 模型: ndwi_otsu_change_baseline v0.1.0
- 数据对齐: EPSG:4526, 10m 网格
- 更新: 2026-07-23
