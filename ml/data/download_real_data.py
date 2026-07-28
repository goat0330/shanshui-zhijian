"""
Download real Sentinel-2 and ancillary data for ML-B1 training.

Downloads for the Chongqing demo AOI:
- Sentinel-2 L2A (T1: 2026-05, T2: 2026-06)
- JRC Global Surface Water occurrence
- ESA WorldCover
- Copernicus DEM

Usage:
    python -m ml.data.download_real_data
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["https_proxy"] = "http://127.0.0.1:7897"

import ee
from ml.data.dataset_registry import DatasetRegistry


AOI_PATH = _ROOT / "data" / "chongqing_demo" / "aoi.geojson"
OUTPUT_DIR = _ROOT / "data" / "chongqing_demo" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

T1_RANGE = ("2026-05-01", "2026-05-31")
T2_RANGE = ("2026-06-01", "2026-06-30")

S2_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
S2_ALIASES = ["blue", "green", "red", "nir", "swir1", "swir2"]
SCALE = 10


def init_gee():
    try:
        ee.Initialize(project="ee-default")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project="ee-default")


def load_aoi(path: Path):
    import json
    with open(path) as f:
        fc = json.load(f)
    coords = fc["features"][0]["geometry"]["coordinates"]
    return ee.Geometry.Polygon(coords)


def mask_clouds(image):
    cs = (
        ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
        .filterBounds(image.geometry())
        .filterDate(image.date())
        .first()
    )
    return image.updateMask(cs.select("cs").gte(0.60))


def build_s2_composite(start_date, end_date, aoi, label):
    print(f"  Building {label} composite ({start_date} ~ {end_date})")
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
        .map(mask_clouds)
    )
    composite = collection.median().select(S2_BANDS, S2_ALIASES).clip(aoi)
    return composite


def download_image(img, out_path, region, scale, crs="EPSG:4326"):
    task = ee.batch.Export.image.toDrive(
        image=img,
        description=out_path.stem,
        folder="geocode_ml_b1",
        fileNamePrefix=out_path.stem,
        scale=scale,
        crs=crs,
        region=region,
        maxPixels=1e9,
    )
    task.start()
    print(f"  Export task started: {out_path.stem}")
    import time
    while task.active():
        time.sleep(10)
        print(f"    Status: {task.status()['state']}")
    status = task.status()
    if status["state"] == "COMPLETED":
        print(f"  Download complete: {out_path.stem}")
    else:
        print(f"  Export failed: {status}")


def download_locally(img, out_path, region, scale, crs="EPSG:4326"):
    """Download via getDownloadURL for small regions."""
    url = img.getDownloadURL(
        region=region,
        scale=scale,
        crs=crs,
        format="GEO_TIFF",
    )
    import requests
    resp = requests.get(url, timeout=300, stream=True)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
    print(f"  Downloaded: {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


def main():
    registry = DatasetRegistry()
    print("=" * 50)
    print("ML-B1: Download Real Data")
    print("=" * 50)

    print("\nVerifying dataset licenses:")
    for ds in registry.list_available():
        result = registry.verify_license(ds.dataset_id)
        status = "OK" if result["ok"] else "NEEDS REVIEW"
        print(f"  [{status}] {ds.dataset_id}: {ds.license}")

    print("\nInitializing GEE...")
    init_gee()
    aoi = load_aoi(AOI_PATH)
    print(f"AOI loaded: {AOI_PATH}")

    print("\n[1/3] Downloading Sentinel-2 composites...")
    t1 = build_s2_composite(T1_RANGE[0], T1_RANGE[1], aoi, "s2_t1")
    t2 = build_s2_composite(T2_RANGE[0], T2_RANGE[1], aoi, "s2_t2")

    for label, img in [("s2_t1", t1), ("s2_t2", t2)]:
        out = OUTPUT_DIR / f"{label}.tif"
        if out.exists():
            print(f"  Already exists: {out}, skipping")
            continue
        try:
            download_locally(img, out, region=aoi, scale=SCALE, crs="EPSG:4326")
        except Exception as e:
            print(f"  Direct download failed ({e}), using async export")
            download_image(img, out, region=aoi, scale=SCALE, crs="EPSG:4326")

    print("\n[2/3] Downloading static ancillary data...")
    ancillary = [
        ("jrc_water_occurrence", "JRC/GSW1_4/GlobalSurfaceWater", ["occurrence"], 30),
        ("worldcover_2021", "ESA/WorldCover/v200", ["Map"], 10),
        ("dem_glo30", "COPERNICUS/DEM/GLO30_2024_1", ["elevation"], 30),
    ]
    for name, gee_id, bands, scale_anc in ancillary:
        out = OUTPUT_DIR / f"{name}.tif"
        if out.exists():
            print(f"  Already exists: {out}, skipping")
            continue
        print(f"  Downloading {name}...")
        img = ee.Image(gee_id).select(bands).clip(aoi)
        try:
            download_locally(img, out, region=aoi, scale=scale_anc, crs="EPSG:4326")
        except Exception as e:
            print(f"  Direct download failed ({e}), using async export")
            download_image(img, out, region=aoi, scale=scale_anc, crs="EPSG:4326")

    print("\n[3/3] Verifying downloads...")
    expected = [
        "s2_t1.tif", "s2_t2.tif",
        "jrc_water_occurrence.tif", "worldcover_2021.tif", "dem_glo30.tif",
    ]
    for name in expected:
        path = OUTPUT_DIR / name
        if path.exists() and path.stat().st_size > 0:
            print(f"  OK: {name} ({path.stat().st_size / 1e6:.1f} MB)")
        else:
            print(f"  MISSING: {name}")

    registry_path = _ROOT / "ml" / "data" / "dataset_registry.json"
    print(f"\nDataset Registry: {registry_path}")
    print("ML-B1 data download complete.")


if __name__ == "__main__":
    main()
