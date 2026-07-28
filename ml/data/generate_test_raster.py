"""Generate a small synthetic GeoTIFF for testing ML-B1 without real GEE data."""

import os
import numpy as np
from pathlib import Path

# Fix PROJ database conflict on Windows with PostgreSQL
_pyproj = Path(__file__).parents[4] / "pyproj" / "proj_dir" / "share" / "proj"
_alt = Path(r"D:\py\Python3\Lib\site-packages\pyproj\proj_dir\share\proj")
if _alt.exists():
    os.environ.setdefault("PROJ_LIB", str(_alt))
elif _pyproj.exists():
    os.environ.setdefault("PROJ_LIB", str(_pyproj))

DATA_DIR = Path(__file__).parent


def main():
    import rasterio
    from rasterio.transform import from_origin

    width, height = 64, 64
    transform = from_origin(106.55, 29.58, 0.0001, 0.0001)
    crs = "EPSG:4326"

    # 6 bands: blue, green, red, nir, swir1, swir2
    rng = np.random.RandomState(42)
    bands = []
    for _ in range(6):
        band = rng.uniform(500, 5000, (height, width)).astype(np.float32)
        # Add water-like pattern (lower reflectance in nir/swir)
        water_mask = rng.random((height, width)) < 0.15
        band[water_mask] = rng.uniform(100, 800, size=water_mask.sum()).astype(np.float32)
        bands.append(band)

    stack = np.stack(bands, axis=0)
    band_names = ["blue", "green", "red", "nir", "swir1", "swir2"]

    s2_path = DATA_DIR / "test_s2_t1.tif"
    with rasterio.open(
        s2_path, "w",
        driver="GTiff", height=height, width=width, count=6,
        dtype=np.float32, crs=crs, transform=transform,
    ) as dst:
        for i, name in enumerate(band_names):
            dst.write(stack[i], i + 1)
            dst.set_band_description(i + 1, name)
    print(f"Test S2 raster: {s2_path}")

    # JRC occurrence (0-100)
    jrc = np.zeros((height, width), dtype=np.float32)
    jrc[water_mask] = rng.uniform(60, 100, size=water_mask.sum()).astype(np.float32)
    jrc[~water_mask] = rng.uniform(0, 30, size=(~water_mask).sum()).astype(np.float32)

    jrc_path = DATA_DIR / "test_jrc_occurrence.tif"
    with rasterio.open(
        jrc_path, "w",
        driver="GTiff", height=height, width=width, count=1,
        dtype=np.float32, crs=crs, transform=transform,
    ) as dst:
        dst.write(jrc, 1)
        dst.set_band_description(1, "occurrence")
    print(f"Test JCR raster: {jrc_path}")

    print("Test rasters generated.")


if __name__ == "__main__":
    main()
