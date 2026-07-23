"""Pipeline 单元测试"""

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from competition.spikes.chongqing_rs_demo.pipeline.io.reader import RasterInput, validate_alignment
from competition.spikes.chongqing_rs_demo.pipeline.features.spectral import compute_ndwi, compute_ndvi
from competition.spikes.chongqing_rs_demo.pipeline.models.baseline_water import local_otsu_threshold, apply_water_mask


def _make_sample(h=10, w=10, val=0.5):
    """构造测试用 RasterInput"""
    arr = np.full((1, h, w), val, dtype=np.float32)
    return RasterInput(
        array=arr,
        crs=CRS.from_epsg(4526),
        transform=from_bounds(106.55, 29.55, 106.60, 29.60, w, h),
        bounds=(106.55, 29.55, 106.60, 29.60),
        bands=["green"],
        width=w,
        height=h,
        nodata=-9999,
        metadata={"test": True},
    )


class TestInputAdapter:
    def test_read_geotiff_creates_rasterinput(self):
        """RasterInput 对象构造正确"""
        ri = _make_sample()
        assert ri.array.shape == (1, 10, 10)
        assert ri.crs == CRS.from_epsg(4526)
        assert ri.width == 10
        assert ri.height == 10

    def test_validate_alignment_same(self):
        """相同网格的输入校验通过"""
        a = _make_sample()
        b = _make_sample()
        assert validate_alignment([a, b])

    def test_validate_alignment_different(self):
        """不同网格的输入校验不通过"""
        a = _make_sample(w=10)
        b = _make_sample(w=20)
        assert not validate_alignment([a, b])


class TestFeatureExtractor:
    def test_ndwi_water_greater_than_zero(self):
        """水体 NDWI 大于 0: green > nir"""
        arr = np.zeros((6, 10, 10), dtype=np.float32)
        arr[1] = 0.3   # green
        arr[3] = 0.05  # nir
        ri = _make_sample()
        ri.array = arr
        ri.bands = ["blue", "green", "red", "nir", "swir1", "swir2"]
        ndwi = compute_ndwi(ri)
        assert ndwi[0, 0] > 0

    def test_ndwi_land_less_than_zero(self):
        """陆地 NDWI 小于 0: green < nir"""
        arr = np.zeros((6, 10, 10), dtype=np.float32)
        arr[1] = 0.1   # green
        arr[3] = 0.35  # nir
        ri = _make_sample()
        ri.array = arr
        ri.bands = ["blue", "green", "red", "nir", "swir1", "swir2"]
        ndwi = compute_ndwi(ri)
        assert ndwi[0, 0] < 0


class TestModelClient:
    def test_local_otsu_produces_threshold(self):
        """局部 Otsu 能计算出有效阈值"""
        np.random.seed(42)
        ndwi = np.random.uniform(-0.5, 0.5, (100, 100)).astype(np.float32)
        ndwi[20:40, 20:40] = 0.6  # 水体区域
        t = local_otsu_threshold(ndwi, grid_size=50)
        assert -0.5 < t < 0.5

    def test_apply_water_mask_produces_binary(self):
        """水体掩膜输出为 0/1 """
        ndwi = np.random.uniform(-0.5, 0.5, (50, 50)).astype(np.float32)
        ndwi[10:30, 10:30] = 0.6
        mask = apply_water_mask(ndwi, threshold=0.3, min_size_pixels=5)
        assert set(np.unique(mask)).issubset({0, 1})
