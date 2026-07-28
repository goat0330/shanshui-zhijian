"""Generate dual-time Sentinel-2 test rasters with known water changes for ML-B2."""

import os
import numpy as np
from pathlib import Path

_pyproj = Path(r"D:\py\Python3\Lib\site-packages\rasterio\proj_data")
if _pyproj.exists():
    os.environ.setdefault("PROJ_LIB", str(_pyproj))

DATA_DIR = Path(__file__).parent


def _water_disk(h, w, cy, cx, r):
    """Return mask of a disk at (cx, cy) with radius r."""
    yy, xx = np.ogrid[:h, :w]
    return ((yy - cy) ** 2 + (xx - cx) ** 2) <= r ** 2


def main():
    import rasterio
    from rasterio.transform import from_origin

    height, width = 100, 100
    # ~10m resolution, covers ~28.5°N, 106.5°E (Chongqing-like area)
    transform = from_origin(106.55, 29.58, 0.0001, 0.0001)
    crs = "EPSG:4326"
    band_names = ["blue", "green", "red", "nir", "swir1", "swir2"]
    rng = np.random.RandomState(42)

    # ---- JRC water occurrence (static label) ----
    jrc = np.zeros((height, width), dtype=np.float32)
    water_t1_mask = _water_disk(height, width, 40, 40, 15) | _water_disk(height, width, 65, 65, 10)
    jrc[water_t1_mask] = rng.uniform(60, 100, size=water_t1_mask.sum()).astype(np.float32)
    jrc[~water_t1_mask] = rng.uniform(0, 30, size=(~water_t1_mask).sum()).astype(np.float32)

    jrc_path = DATA_DIR / "test_jrc_occurrence.tif"
    with rasterio.open(jrc_path, "w", driver="GTiff", height=height, width=width,
                       count=1, dtype=np.float32, crs=crs, transform=transform) as dst:
        dst.write(jrc, 1)
        dst.set_band_description(1, "occurrence")
    print(f"JRC: {jrc_path}")

    # ---- Water T2 mask: one disk shifts, one new disk appears ----
    water_t2_mask = _water_disk(height, width, 45, 35, 15) | _water_disk(height, width, 30, 70, 8)
    gain_mask = water_t2_mask & ~water_t1_mask
    loss_mask = water_t1_mask & ~water_t2_mask
    persistent_mask = water_t1_mask & water_t2_mask
    print(f"Water T1: {water_t1_mask.sum()} px, T2: {water_t2_mask.sum()} px")
    print(f"Gain: {gain_mask.sum()}, Loss: {loss_mask.sum()}, Persistent: {persistent_mask.sum()}")

    def _make_s2_raster(water_mask):
        """Generate 6-band Sentinel-2-like raster with water/non-water spectral contrast."""
        bands = []
        water_factor_by_band = [0.6, 0.7, 0.3, 0.05, 0.05, 0.05]
        for band_idx, (base_refl, wf) in enumerate(zip(
            [800, 900, 600, 3000, 1500, 1000], water_factor_by_band
        )):
            band = rng.normal(base_refl, 200, (height, width)).astype(np.float32)
            band = np.clip(band, 0, 10000)
            band[water_mask] = (band[water_mask] * wf).clip(0, 10000)
            bands.append(band)
        return np.stack(bands, axis=0)

    t1_array = _make_s2_raster(water_t1_mask)
    t1_path = DATA_DIR / "test_s2_t1.tif"
    with rasterio.open(t1_path, "w", driver="GTiff", height=height, width=width,
                       count=6, dtype=np.float32, crs=crs, transform=transform) as dst:
        for i, name in enumerate(band_names):
            dst.write(t1_array[i], i + 1)
            dst.set_band_description(i + 1, name)
    print(f"S2 T1: {t1_path}")

    t2_array = _make_s2_raster(water_t2_mask)
    t2_path = DATA_DIR / "test_s2_t2.tif"
    with rasterio.open(t2_path, "w", driver="GTiff", height=height, width=width,
                       count=6, dtype=np.float32, crs=crs, transform=transform) as dst:
        for i, name in enumerate(band_names):
            dst.write(t2_array[i], i + 1)
            dst.set_band_description(i + 1, name)
    print(f"S2 T2: {t2_path}")

    # ---- Ground truth change mask for validation ----
    gt_path = DATA_DIR / "test_change_gt.tif"
    gt = np.zeros((height, width), dtype=np.uint8)
    gt[gain_mask] = 1   # gain
    gt[loss_mask] = 2   # loss
    gt[persistent_mask] = 3  # persistent
    with rasterio.open(gt_path, "w", driver="GTiff", height=height, width=width,
                       count=1, dtype=np.uint8, crs=crs, transform=transform) as dst:
        dst.write(gt, 1)
        dst.set_band_description(1, "gt_change")
    print(f"Change GT: {gt_path}")

    print("Test rasters generated successfully.")


if __name__ == "__main__":
    main()
