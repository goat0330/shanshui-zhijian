"""Generate deterministic, co-registered Sentinel-2/JRC test fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).parent


def _water_disk(height: int, width: int, center_y: int, center_x: int, radius: int) -> np.ndarray:
    yy, xx = np.ogrid[:height, :width]
    return ((yy - center_y) ** 2 + (xx - center_x) ** 2) <= radius**2


def main() -> None:
    import rasterio
    from rasterio.transform import from_origin

    height = width = 100
    transform = from_origin(106.55, 29.58, 0.0001, 0.0001)
    crs = "EPSG:4326"
    band_names = ["blue", "green", "red", "nir", "swir1", "swir2"]
    rng = np.random.RandomState(42)

    water_t1 = _water_disk(height, width, 40, 40, 15) | _water_disk(height, width, 65, 65, 10)
    water_t2 = _water_disk(height, width, 45, 35, 15) | _water_disk(height, width, 30, 70, 8)

    jrc = np.zeros((height, width), dtype=np.float32)
    jrc[water_t1] = rng.uniform(60, 100, size=water_t1.sum()).astype(np.float32)
    jrc[~water_t1] = rng.uniform(0, 30, size=(~water_t1).sum()).astype(np.float32)
    jrc_path = DATA_DIR / "test_jrc_occurrence.tif"
    with rasterio.open(
        jrc_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(jrc, 1)
        dst.set_band_description(1, "occurrence")

    def make_s2(water_mask: np.ndarray) -> np.ndarray:
        bands = []
        water_factors = [0.6, 0.7, 0.3, 0.05, 0.05, 0.05]
        for base, factor in zip([800, 900, 600, 3000, 1500, 1000], water_factors):
            band = np.clip(rng.normal(base, 200, (height, width)), 0, 10000).astype(np.float32)
            band[water_mask] = np.clip(band[water_mask] * factor, 0, 10000)
            bands.append(band)
        return np.stack(bands)

    for name, mask, acquisition_date in (
        ("test_s2_t1.tif", water_t1, "2026-05-15T00:00:00Z"),
        ("test_s2_t2.tif", water_t2, "2026-06-15T00:00:00Z"),
    ):
        array = make_s2(mask)
        path = DATA_DIR / name
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=6,
            dtype="float32",
            crs=crs,
            transform=transform,
            nodata=-9999.0,
        ) as dst:
            for index, band_name in enumerate(band_names, start=1):
                dst.write(array[index - 1], index)
                dst.set_band_description(index, band_name)
            dst.update_tags(ACQUISITION_DATE=acquisition_date)

    gain = water_t2 & ~water_t1
    loss = water_t1 & ~water_t2
    persistent = water_t1 & water_t2
    ground_truth = np.zeros((height, width), dtype=np.uint8)
    ground_truth[gain] = 1
    ground_truth[loss] = 2
    ground_truth[persistent] = 3
    with rasterio.open(
        DATA_DIR / "test_change_gt.tif",
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform,
        nodata=255,
    ) as dst:
        dst.write(ground_truth, 1)
        dst.set_band_description(1, "gt_change")

    print(f"Generated fixtures in {DATA_DIR}")
    print(f"T1 water={int(water_t1.sum())}; T2 water={int(water_t2.sum())}")
    print(f"Gain={int(gain.sum())}; Loss={int(loss.sum())}; Persistent={int(persistent.sum())}")


if __name__ == "__main__":
    main()
