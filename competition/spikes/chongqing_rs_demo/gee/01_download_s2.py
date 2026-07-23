"""
山水智鉴 — 下载重庆朝天门 Sentinel-2 L2A 双时相数据

时间:
  T1: 2026-05-01 ~ 2026-05-31
  T2: 2026-06-01 ~ 2026-06-30

波段: B2(蓝), B3(绿), B4(红), B8(近红外), B11(SWIR1), B12(SWIR2)
合成方式: 中位数合成 + Cloud Score+ 质量屏蔽
输出: 多波段 GeoTIFF, 统一 CRS/transform/size
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

BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
BAND_NAMES = ["blue", "green", "red", "nir", "swir1", "swir2"]
SCALE = 10
CRS = "EPSG:4326"  # 先下 WGS84, Pipeline 里重投影到 EPSG:4526


def mask_clouds(image):
    """用 Cloud Score+ 屏蔽低质量像元"""
    cloud_score = (
        ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
        .filterBounds(image.geometry())
        .filterDate(image.date())
        .first()
    )
    quality_mask = cloud_score.select("cs").gte(0.60)
    return image.updateMask(quality_mask)


def build_composite(start_date, end_date, aoi, label):
    """构建一期中位数合成"""
    with heartbeat(f"Building {label} composite ({start_date} ~ {end_date})"):
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
            .map(mask_clouds)
        )
        composite = collection.median().select(BANDS, BAND_NAMES).clip(aoi)
    return composite


def main():
    init_gee()

    with heartbeat("Loading AOI"):
        aoi_fc = load_region(AOI_PATH)
        aoi = aoi_fc.geometry()

    # 构建两期合成
    t1 = build_composite(T1_START, T1_END, aoi, "T1")
    t2 = build_composite(T2_START, T2_END, aoi, "T2")

    # 下载
    for label, img in [("s2_t1", t1), ("s2_t2", t2)]:
        out_path = str(OUTPUT_DIR / f"{label}.tif")
        with heartbeat(f"Downloading {label} to {out_path}"):
            download_image(img, out_path, region=aoi, scale=SCALE, crs=CRS)
        print(f"✅ {label} saved to {out_path}")

    print("✅ Sentinel-2 双时相下载完成")


if __name__ == "__main__":
    main()
