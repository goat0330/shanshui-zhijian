# 山水智鉴 V0 — 重庆两江真实遥感数据全链路原型

## 定位
用重庆真实遥感数据，跑通从数据下载到人工核验的完整链路，验证"模型和业务解耦"的架构假设。

## 数据
| 数据集 | 来源 | 分辨率 | 时间 |
|--------|------|--------|------|
| Sentinel-2 L2A | GEE COPERNICUS/S2_SR_HARMONIZED | 10m | T1: 2026-05, T2: 2026-06 |
| Sentinel-1 GRD | GEE COPERNICUS/S1_GRD | 10m | T1: 2026-05, T2: 2026-06 |
| DEM | COPERNICUS/DEM/GLO30 | 30m | 静态 |
| 稳定水体 | JRC/GSW1_4/GlobalSurfaceWater | 30m | 1984-2021 |
| 土地覆盖 | ESA/WorldCover/v200 | 10m | 2021 |

## 诚实声明
- 所有结果为**算法候选**，非政府认定的违法或"四乱"事件
- 所有角色为**演练角色**，非真实部门用户
- 置信度为**规则分数**，非统计概率
- 数据来源全部标注为"公开数据和算法派生"

## 运行
```bash
# 1. GEE 数据下载
python gee/01_download_s2.py
python gee/02_download_s1.py
python gee/03_download_context.py

# 2. 运行 Pipeline
python pipeline/run_pipeline.py
```
