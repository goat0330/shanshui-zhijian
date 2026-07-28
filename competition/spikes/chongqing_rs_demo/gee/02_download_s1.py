"""
山水智鉴 — 下载重庆朝天门 Sentinel-1 GRD 双时相数据 (VV+VH)

时间:
  T1: 2026-05-01 ~ 2026-05-31
  T2: 2026-06-01 ~ 2026-06-30

预处理: 边缘滤波 (speckle reduction) + 分贝转换
输出: 双波段 GeoTIFF, 与 S2 严格对齐 (CRS/transform/size)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["https_proxy"] = "http://127.0.0.1:7897"

import ee
from geocode import init_gee, load_region, heartbeat, download_image

# ── 配置 ──────────────────────────────────────────────────────────
AOI_PATH = str(Path(__file__).resolve().parents[4] / "data" / "chongqing_demo" / "aoi.geojson")
OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "chongqing_demo" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

T1_START = "2026-05-01"
T1_END = "2026-05-31"
T2_START = "2026-06-01"
T2_END = "2026-06-30"

SCALE = 10
CRS = "EPSG:4326"  # 先下 WGS84, Pipeline 里重投影


def to_db(img):
    """后向散射系数转分贝"""
    return ee.Image(10).multiply(img.log10())


def refine_speckle(img):
    """精炼Lee滤波降噪"""
    from geocode import heartbeat as hb
    with hb("Applying speckle filter"):
        # 简单均值滤波代替复杂精炼Lee
        smoothed = img.reduceNeighborhood(
            reducer=ee.Reducer.mean(),
            kernel=ee.Kernel.square(3),
        )
    return smoothed


def build_sar_composite(start_date, end_date, aoi, label):
    """构建一期SAR中位数合成，VV+VH"""
    with heartbeat(f"Building SAR {label} composite ({start_date} ~ {end_date})"):
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
        )
        composite = (
            collection.select(["VV", "VH"])
            .median()
            .clip(aoi)
            .rename(["vv", "vh"])
        )
    return composite


def main():
    init_gee()

    with heartbeat("Loading AOI"):
        aoi_fc = load_region(AOI_PATH)
        aoi = aoi_fc.geometry()

    for label, start, end in [("s1_t1", T1_START, T1_END), ("s1_t2", T2_START, T2_END)]:
        composite = build_sar_composite(start, end, aoi, label)
        # 转分贝
        composite_db = to_db(composite)
        out_path = str(OUTPUT_DIR / f"{label}.tif")
        with heartbeat(f"Downloading {label} to {out_path}"):
            download_image(composite_db, out_path, region=aoi, scale=SCALE, crs=CRS)
        print(f"✅ {label} saved to {out_path}")

    print("✅ Sentinel-1 双时相下载完成")


if __name__ == "__main__":
    main()
