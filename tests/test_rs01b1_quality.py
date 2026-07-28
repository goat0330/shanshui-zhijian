"""
RS-01B-1 综合测试

覆盖:
1. SarMetadata 契约
2. SarValidationPolicy 策略解析
3. QualityReport 扩展字段
4. 质量指标计算
5. 质量校验 (7 类场景)
6. 集成工具 + 质量门禁
7. 重庆合格数据回归 vs RS-01A.2 baseline
"""

import json
import sys
import tempfile
import shutil
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from pydantic import ValidationError as PydanticValidationError

from core.schemas.contracts import (
    Modality, AssetRole, ExecutionStatus, TaskType,
)
from core.schemas.contracts.asset import AssetRef
from core.schemas.contracts.task import (
    TaskAssetBinding, InputSlotSpec, TaskSpec, InferenceTask, RunContext,
)
from core.schemas.contracts.perception import Observation, QualityReport
from core.schemas.contracts.sar_metadata import SarMetadata
from core.schemas.contracts.validation_policy import (
    SarValidationPolicy, PolicyMode,
    OrbitPolicy, OrbitDirectionPolicy,
    MissingOrbitMetadata, MissingRequiredBand, RegistrationPolicy,
)
from core.protocols.asset_resolver import AssetRegistry
from tools.sar_quality_validator import (
    compute_input_quality, validate_sar_input, ValidationResult,
)
from tools.sar_temporal_change_tool import SarTemporalChangeTool


# ── Fixtures ─────────────────────────────────────────────────

def _make_sar_tiff(path: Path, width=64, height=64,
                   vv_val=-8.0, vh_val=-15.0,
                   nodata=-9999.0, add_noise=True, water_rect=None):
    """创建合成双波段 SAR GeoTIFF (VV+VH)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    vv = np.full((height, width), vv_val, dtype=np.float32)
    vh = np.full((height, width), vh_val, dtype=np.float32)
    if water_rect:
        x1, y1, x2, y2 = water_rect
        vv[y1:y2, x1:x2] = -15.0
        vh[y1:y2, x1:x2] = -22.0
    if add_noise:
        vv += np.random.normal(0, 0.5, (height, width)).astype(np.float32)
        vh += np.random.normal(0, 0.5, (height, width)).astype(np.float32)
    transform = from_bounds(106.55, 29.55, 106.60, 29.60, width, height)
    with rasterio.open(path, "w", driver="GTiff", height=height, width=width,
                       count=2, dtype="float32", crs="EPSG:4326",
                       transform=transform, nodata=nodata, compress="lzw") as dst:
        dst.write(vv, 1)
        dst.write(vh, 2)
        dst.set_band_description(1, "VV")
        dst.set_band_description(2, "VH")
    return path


def _make_all_nodata_tiff(path: Path, width=32, height=32) -> Path:
    """创建全 nodata 的 TIFF。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.full((2, height, width), -9999.0, dtype=np.float32)
    transform = from_bounds(106.0, 29.0, 106.05, 29.05, width, height)
    with rasterio.open(path, "w", driver="GTiff", height=height, width=width,
                       count=2, dtype="float32", crs="EPSG:4326",
                       transform=transform, nodata=-9999.0, compress="lzw") as dst:
        dst.write(arr[0], 1)
        dst.write(arr[1], 2)
    return path


def _make_constant_tiff(path: Path, width=32, height=32) -> Path:
    """创建全常量像素 TIFF。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.full((2, height, width), -10.0, dtype=np.float32)
    transform = from_bounds(106.0, 29.0, 106.05, 29.05, width, height)
    with rasterio.open(path, "w", driver="GTiff", height=height, width=width,
                       count=2, dtype="float32", crs="EPSG:4326",
                       transform=transform, nodata=-9999.0, compress="lzw") as dst:
        dst.write(arr[0], 1)
        dst.write(arr[1], 2)
    return path


# ── Test SarMetadata ─────────────────────────────────────────

class TestSarMetadata:
    def test_minimal_metadata(self):
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=98,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-15T10:30:00Z",
        )
        assert meta.platform == "Sentinel-1A"
        assert meta.is_same_orbit(meta)
        assert meta.has_vv and meta.has_vh
        assert meta.missing_fields() == []

    def test_missing_fields(self):
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="UNKNOWN", relative_orbit=-1,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-15T10:30:00Z",
        )
        assert "orbit_direction" in meta.missing_fields()
        assert "relative_orbit" in meta.missing_fields()

    def test_same_orbit(self):
        a = SarMetadata(platform="S1A", product_type="GRD", processing_level="L1",
                        orbit_direction="ASCENDING", relative_orbit=98,
                        polarizations=["VV", "VH"], incidence_angle_min=30.0,
                        incidence_angle_max=46.0, acquisition_time="2024-01-15")
        b = SarMetadata(platform="S1A", product_type="GRD", processing_level="L1",
                        orbit_direction="ASCENDING", relative_orbit=98,
                        polarizations=["VV", "VH"], incidence_angle_min=31.0,
                        incidence_angle_max=47.0, acquisition_time="2024-02-01")
        assert a.is_same_orbit(b)

    def test_cross_orbit(self):
        a = SarMetadata(platform="S1A", product_type="GRD", processing_level="L1",
                        orbit_direction="ASCENDING", relative_orbit=98,
                        polarizations=["VV", "VH"], incidence_angle_min=30.0,
                        incidence_angle_max=46.0, acquisition_time="2024-01-15")
        b = SarMetadata(platform="S1A", product_type="GRD", processing_level="L1",
                        orbit_direction="DESCENDING", relative_orbit=62,
                        polarizations=["VV", "VH"], incidence_angle_min=30.0,
                        incidence_angle_max=46.0, acquisition_time="2024-02-01")
        assert not a.is_same_orbit(b)

    def test_from_asset_ref(self):
        asset = AssetRef(asset_id="test_sar", uri="/data/s1a_vv_vh.tif",
                         media_type="image/tiff", modality=Modality.SAR,
                         bands=["vv", "vh"], acquisition_time="2024-01-15T10:30:00Z")
        meta = SarMetadata.from_asset_ref(asset, "/data/s1a_vv_vh.tif")
        assert meta.polarizations == ["VV", "VH"]
        assert meta.has_vv and meta.has_vh


# ── Test SarValidationPolicy ─────────────────────────────────

class TestValidationPolicy:
    def test_default_strict(self):
        p = SarValidationPolicy.default_strict()
        assert p.mode == PolicyMode.STRICT
        assert p.rejects_on()

    def test_warn_mode(self):
        p = SarValidationPolicy.default_warn()
        assert p.mode == PolicyMode.WARN
        assert not p.rejects_on()
        assert p.allows_rejection()

    def test_trust_mode(self):
        p = SarValidationPolicy.trust_only()
        assert p.mode == PolicyMode.TRUST
        assert not p.rejects_on()

    def test_from_dict(self):
        d = {"mode": "warn", "orbit_policy": "allow_cross",
             "missing_orbit_metadata": "warn", "required_polarizations": ["VV"]}
        p = SarValidationPolicy(**d)
        assert p.mode == PolicyMode.WARN
        assert p.orbit_policy == OrbitPolicy.ALLOW_CROSS
        assert p.required_polarizations == ["VV"]


# ── Test Quality Metrics ─────────────────────────────────────

class TestQualityMetrics:
    def test_identical_images(self, tmp_path):
        """相同图像: 质量指标应该接近 1.0。"""
        t1 = _make_sar_tiff(tmp_path / "t1.tif")
        t2 = _make_sar_tiff(tmp_path / "t2.tif")
        with rasterio.open(t1) as src1, rasterio.open(t2) as src2:
            arr1 = src1.read()
            arr2 = src2.read()
            # 使用相同数据模拟完美重叠
            metrics = compute_input_quality(arr1, arr1, ["vv", "vh"], ["vv", "vh"])
        assert metrics["valid_pixel_ratio"] > 0.5
        assert metrics["nodata_ratio"] < 0.5
        assert metrics["finite_pixel_ratio"] > 0.5

    def test_all_nodata(self, tmp_path):
        """全 nodata: valid_pixel_ratio ≈ 0。"""
        t1 = _make_all_nodata_tiff(tmp_path / "all_nodata.tif")
        with rasterio.open(t1) as src:
            arr = src.read()
            metrics = compute_input_quality(arr, arr, ["vv", "vh"], ["vv", "vh"])
        assert metrics["valid_pixel_ratio"] < 0.01
        assert metrics["nodata_ratio"] > 0.99

    def test_dynamic_range(self, tmp_path):
        """检查 VV/VH 动态范围计算。"""
        path = tmp_path / "synthetic.tif"
        path.parent.mkdir(parents=True, exist_ok=True)
        vv = np.array([[ -12.0,  -5.0], [ -3.0,  -1.0]], dtype=np.float32)
        vh = np.array([[ -20.0, -15.0], [-22.0, -10.0]], dtype=np.float32)
        with rasterio.open(path, "w", driver="GTiff", height=2, width=2,
                           count=2, dtype="float32", crs="EPSG:4326",
                           transform=from_bounds(0, 0, 1, 1, 2, 2), nodata=-9999.0) as dst:
            dst.write(vv, 1)
            dst.write(vh, 2)
        with rasterio.open(path) as src:
            arr = src.read()
            metrics = compute_input_quality(arr, arr, ["vv", "vh"], ["vv", "vh"])
        vv_range = metrics["vv_dynamic_range"]
        vh_range = metrics["vh_dynamic_range"]
        assert vv_range is not None
        assert vh_range is not None
        assert abs(vv_range[0] - (-12.0)) < 1.0
        assert abs(vh_range[0] - (-22.0)) < 1.0


# ── Test Validation Logic ─────────────────────────────────────

def _make_metadata(**overrides) -> SarMetadata:
    defaults = dict(platform="Sentinel-1A", product_type="GRD", processing_level="L1",
                    orbit_direction="ASCENDING", relative_orbit=98,
                    polarizations=["VV", "VH"], incidence_angle_min=30.0,
                    incidence_angle_max=46.0, acquisition_time="2024-01-15T10:30:00Z")
    defaults.update(overrides)
    return SarMetadata(**defaults)


class TestValidation:
    def test_same_orbit_passes(self):
        """同轨 + 合格质量应通过。"""
        meta = _make_metadata()
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.8}
        result = validate_sar_input(meta, meta, ["vv", "vh"], ["vv", "vh"],
                                    quality, SarValidationPolicy.default_strict(), 64, 64, 64, 64)
        assert result.passed
        assert result.quality.orbit_match is True

    def test_cross_orbit_rejected_strict(self):
        """跨轨 + strict 应被拒绝。"""
        meta_a = _make_metadata(orbit_direction="ASCENDING", relative_orbit=98)
        meta_b = _make_metadata(orbit_direction="DESCENDING", relative_orbit=62)
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.8}
        result = validate_sar_input(meta_a, meta_b, ["vv", "vh"], ["vv", "vh"],
                                    quality, SarValidationPolicy.default_strict(), 64, 64, 64, 64)
        assert not result.passed
        assert result.rejection_reason is not None

    def test_cross_orbit_warn(self):
        """跨轨 + warn 应通过但有警告。"""
        meta_a = _make_metadata(orbit_direction="ASCENDING", relative_orbit=98)
        meta_b = _make_metadata(orbit_direction="DESCENDING", relative_orbit=62)
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.8}
        result = validate_sar_input(meta_a, meta_b, ["vv", "vh"], ["vv", "vh"],
                                    quality, SarValidationPolicy.default_warn(), 64, 64, 64, 64)
        assert result.passed
        assert len(result.quality.reasons) >= 1 or len(result.quality.recommendations) >= 1

    def test_missing_metadata_rejected(self):
        """缺失轨道元数据 + reject 策略应被拒绝。"""
        meta = _make_metadata(orbit_direction="UNKNOWN", relative_orbit=-1)
        policy = SarValidationPolicy(mode="strict", missing_orbit_metadata="reject")
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.8}
        result = validate_sar_input(meta, meta, ["vv", "vh"], ["vv", "vh"],
                                    quality, policy, 64, 64, 64, 64)
        assert not result.passed

    def test_missing_metadata_warn(self):
        """缺失元数据 + warn 应通过。"""
        meta = _make_metadata(orbit_direction="UNKNOWN", relative_orbit=-1)
        policy = SarValidationPolicy(mode="strict", missing_orbit_metadata="warn")
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.8}
        result = validate_sar_input(meta, meta, ["vv", "vh"], ["vv", "vh"],
                                    quality, policy, 64, 64, 64, 64)
        assert result.passed

    def test_missing_vh_rejected(self):
        """缺失 VH 应被拒绝。"""
        meta = _make_metadata()
        policy = SarValidationPolicy(mode="strict", required_polarizations=["VV", "VH"])
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.8}
        result = validate_sar_input(meta, meta, ["vv"], ["vv"],
                                    quality, policy, 64, 64, 64, 64)
        assert not result.passed

    def test_low_valid_pixels_rejected(self):
        """有效像元比 < 0.1 应被拒绝。"""
        meta = _make_metadata()
        policy = SarValidationPolicy(mode="strict", minimum_valid_pixel_ratio=0.1)
        quality = {"valid_pixel_ratio": 0.01, "spatial_overlap_ratio": 0.01}
        result = validate_sar_input(meta, meta, ["vv", "vh"], ["vv", "vh"],
                                    quality, policy, 64, 64, 64, 64)
        assert not result.passed

    def test_low_spatial_overlap_rejected(self):
        """空间重叠比 < 0.5 应被拒绝。"""
        meta = _make_metadata()
        policy = SarValidationPolicy(mode="strict", minimum_spatial_overlap_ratio=0.5)
        quality = {"valid_pixel_ratio": 0.8, "spatial_overlap_ratio": 0.3}
        result = validate_sar_input(meta, meta, ["vv", "vh"], ["vv", "vh"],
                                    quality, policy, 64, 64, 64, 64)
        assert not result.passed

    def test_trust_always_passes(self):
        """trust 模式无论输入质量如何都应通过。"""
        meta = _make_metadata(orbit_direction="ASCENDING", relative_orbit=98)
        meta_b = _make_metadata(orbit_direction="DESCENDING", relative_orbit=62)
        quality = {"valid_pixel_ratio": 0.0, "spatial_overlap_ratio": 0.0}
        result = validate_sar_input(meta, meta_b, ["vv"], ["vv"],
                                    quality, SarValidationPolicy.trust_only(), 64, 64, 100, 100)
        assert result.passed


# ── Test Integrated Tool with Quality Gate ────────────────────

class TestToolQualityGate:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.t1 = _make_sar_tiff(self.tmpdir / "s1_t1.tif", 64, 64,
                                  water_rect=(0, 0, 16, 16))
        self.t2 = _make_sar_tiff(self.tmpdir / "s1_t2.tif", 64, 64,
                                  water_rect=(0, 0, 32, 32))
        self.output = self.tmpdir / "out"
        yield
        shutil.rmtree(self.tmpdir)

    def _make_assets(self) -> AssetRegistry:
        return AssetRegistry([
            AssetRef(asset_id="before", uri=str(self.t1),
                     media_type="image/tiff; application=geotiff",
                     modality=Modality.SAR, bands=["vv", "vh"]),
            AssetRef(asset_id="after", uri=str(self.t2),
                     media_type="image/tiff; application=geotiff",
                     modality=Modality.SAR, bands=["vv", "vh"]),
        ])

    def _run_tool(self, registry=None, spec_overrides=None):
        registry = registry or self._make_assets()
        tool = SarTemporalChangeTool(registry=registry)
        task = InferenceTask(
            task_id="qb-task", sample_id="qb-001", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="after", role=AssetRole.AFTER),
            ],
        )
        policy = spec_overrides or {}
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1", version="1.0.0",
            task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
            validation_policy=policy,
        )
        ctx = RunContext(run_id="qb-run", output_dir=str(self.output))
        return tool.run(task, spec, ctx)

    def test_tool_with_default_strict_passes(self):
        """warn 策略 + 合格合成数据应成功 (合成数据缺元数据, strict 会拒绝)。"""
        result = self._run_tool(spec_overrides={"mode": "warn"})
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS

    def test_tool_strict_rejects_low_quality(self, tmp_path):
        """strict + 低质量数据应被拒绝。"""
        # 全 nodata
        all_nodata = tmp_path / "nodata.tif"
        _make_all_nodata_tiff(all_nodata)
        registry = AssetRegistry([
            AssetRef(asset_id="before", uri=str(all_nodata),
                     media_type="image/tiff; application=geotiff",
                     modality=Modality.SAR, bands=["vv", "vh"]),
            AssetRef(asset_id="after", uri=str(all_nodata),
                     media_type="image/tiff; application=geotiff",
                     modality=Modality.SAR, bands=["vv", "vh"]),
        ])
        result = self._run_tool(registry=registry, spec_overrides={"mode": "strict"})
        assert result.status in (ExecutionStatus.NO_DATA, ExecutionStatus.INVALID_INPUT)
        assert result.quality_report is not None

    def test_tool_warn_pass(self):
        """warn 模式不应拒绝合格数据。"""
        result = self._run_tool(spec_overrides={"mode": "warn"})
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS

    def test_tool_trust_pass(self):
        """trust 模式直接运行。"""
        result = self._run_tool(spec_overrides={"mode": "trust_preprocessed_input"})
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS


# ── Regression vs RS-01A.2 ───────────────────────────────────

class TestRegression:
    """重庆合格数据回归: RS-01B-1 quality gate 不得改变输出。"""

    RAW_DIR = ROOT / "data" / "chongqing_demo" / "raw"
    HAS_DATA = (RAW_DIR / "s1_t1.tif").exists() and (RAW_DIR / "s1_t2.tif").exists()

    @pytest.mark.skipif(not HAS_DATA, reason="重庆真实数据不存在")
    def test_quality_gate_passes_and_unchanged(self):
        """质量门禁通过，输出不得改变。"""
        registry = AssetRegistry([
            AssetRef(asset_id="real_t1", uri=str(self.RAW_DIR / "s1_t1.tif"),
                     media_type="image/tiff; application=geotiff",
                     modality=Modality.SAR, bands=["vv", "vh"]),
            AssetRef(asset_id="real_t2", uri=str(self.RAW_DIR / "s1_t2.tif"),
                     media_type="image/tiff; application=geotiff",
                     modality=Modality.SAR, bands=["vv", "vh"]),
        ])
        tool = SarTemporalChangeTool(registry=registry)
        task = InferenceTask(
            task_id="reg-b1", sample_id="reg-b1", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="real_t1", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="real_t2", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1", version="1.0.0",
            task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
            validation_policy={"mode": "warn"},  # 不因元数据未知而拒绝
        )
        tmp = Path(tempfile.mkdtemp())
        ctx = RunContext(run_id="reg-b1-run", output_dir=str(tmp))
        result = tool.run(task, spec, ctx)

        # 必须成功 (warn 模式不拒绝)
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS, \
            f"回归失败: status={result.status}"
        assert result.diagnostics.get("total_changed_pixels", 0) > 0, "应有变化像元"
        assert result.diagnostics.get("total_changed_pixels") == 10498, \
            f"变化像元应与 baseline 一致, 期望 10498, 实际 {result.diagnostics.get('total_changed_pixels')}"
        assert result.diagnostics.get("polygon_count") == 510, \
            f"多边形数应与 baseline 一致, 期望 510, 实际 {result.diagnostics.get('polygon_count')}"

        shutil.rmtree(tmp)
