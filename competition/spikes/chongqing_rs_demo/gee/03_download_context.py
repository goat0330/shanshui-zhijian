"""
山水智鉴 — 下载辅助上下文数据 (静态/准静态)

- DEM: Copernicus GLO-30 (30m)
- 稳定水体: JRC GSW occurrence (30m)
- 土地覆盖: ESA WorldCover v200 (10m)

所有输出对齐到 S2 的 CRS/transform/size (由 S2 参考栅格决定)
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

SCALE = 10
CRS = "EPSG:4326"  # 先下 WGS84, Pipeline 里重投影


def main():
    init_gee()

    with heartbeat("Loading AOI"):
        aoi_fc = load_region(AOI_PATH)
        aoi = aoi_fc.geometry()

    # ── DEM ──────────────────────────────────────────────────────
    with heartbeat("Processing DEM"):
        dem = (
            ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1")
            .mosaic()
            .select("DEM")
            .clip(aoi)
            .float()
        )
        download_image(dem, str(OUTPUT_DIR / "dem_glo30.tif"), region=aoi, scale=30, crs=CRS)
        print("✅ DEM saved")

    # ── JRC 稳定水体 (occurrence) ────────────────────────────────
    with heartbeat("Processing JRC water occurrence"):
        jrc = (
            ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
            .select("occurrence")
            .clip(aoi)
        )
        download_image(jrc, str(OUTPUT_DIR / "jrc_water_occurrence.tif"), region=aoi, scale=30, crs=CRS)
        print("✅ JRC water occurrence saved")

    # ── ESA WorldCover ───────────────────────────────────────────
    with heartbeat("Processing ESA WorldCover"):
        wc = (
            ee.Image("ESA/WorldCover/v200")
            .select("Map")
            .clip(aoi)
        )
        download_image(wc, str(OUTPUT_DIR / "worldcover_2021.tif"), region=aoi, scale=10, crs=CRS)
        print("✅ WorldCover saved")

    print("✅ 所有上下文数据下载完成")


if __name__ == "__main__":
    main()
