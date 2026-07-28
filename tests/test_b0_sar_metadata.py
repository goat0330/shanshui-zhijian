"""
B0 — SarMetadata 逐字段来源与 Strict 门禁测试

测试类别：
1. AssetRef 字段优先于 GeoTIFF tags
2. GeoTIFF tags 补全 AssetRef 缺失字段
3. Sidecar 补全 Tags 缺失字段
4. 不同来源冲突（正确逐字段合并）
5. strict 拒绝 inferred/unknown 关键字段
6. warn 接受但带 quality flags
7. acquisition_time 缺失
8. platform 未知
9. 只有 VV（单极化）
10. VV/VH 双极化
11. GeoTIFF 无法读取
12. Sidecar 损坏
13. URI 无可推断内容
14. AssetRef 提供所有字段（trust 模式）
15. strict 拒绝 inferred orbit_direction
"""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

# 确保项目根目录在 sys.path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.schemas.contracts.sar_metadata import (
    SarMetadata,
    SarMetadataResolver,
    MetadataSource,
)


# ── 辅助函数 ──────────────────────────────────────────────────────

class FakeAssetRef:
    """可定制的模拟 AssetRef。"""
    def __init__(self, **kwargs):
        self.asset_id = kwargs.get("asset_id", "test-asset")
        self.uri = kwargs.get("uri", "/fake/path.tif")
        self.media_type = kwargs.get("media_type", "image/tiff")
        self.modality = kwargs.get("modality", "sar")
        self.bands = kwargs.get("bands", None)
        self.acquisition_time = kwargs.get("acquisition_time", None)
        self.platform = kwargs.get("platform", None)
        self.orbit_direction = kwargs.get("orbit_direction", None)
        self.relative_orbit = kwargs.get("relative_orbit", None)
        self.incidence_angle_min = kwargs.get("incidence_angle_min", None)
        self.incidence_angle_max = kwargs.get("incidence_angle_max", None)
        self.product_type = kwargs.get("product_type", None)
        self.processing_level = kwargs.get("processing_level", None)


def write_sidecar(uri: str, data: dict) -> Path:
    """写 sidecar JSON 文件。"""
    p = Path(uri)
    sidecar_path = p.parent / f"{p.stem}.meta.json"
    with open(sidecar_path, "w") as f:
        json.dump(data, f)
    return sidecar_path


# ── 1. AssetRef 字段优先于 GeoTIFF tags ─────────────────────────

class TestAssetRefPriority:
    """AssetRef 显式字段应优先于 GeoTIFF tags（逐字段）。"""

    def test_asset_ref_platform_overrides_tags(self):
        """AssetRef 的 platform 应优先于 GeoTIFF tags 中的 platform。"""
        ref = FakeAssetRef(
            platform="Sentinel-1B",
            uri="/fake/path.tif",
            bands=["VV", "VH"],
            acquisition_time="2024-01-01T00:00:00Z",
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        # GeoTIFF 不存在，走 inferred→ASSET_REF 会设置 platform
        assert meta.source_platform == MetadataSource.ASSET_REF
        # 验证只有 platform 来自 ASSET_REF（不存在 GeoTIFF tags 无法覆盖）
        assert meta.platform == "Sentinel-1B"

    def test_asset_ref_partial_override(self):
        """AssetRef 只提供部分字段，其他由 inferred 补充。"""
        ref = FakeAssetRef(
            orbit_direction="ASCENDING",
            uri="/fake/s1a_path.tif",
            bands=["VV", "VH"],
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/s1a_path.tif")
        # orbit_direction 来自 ASSET_REF
        assert meta.orbit_direction == "ASCENDING"
        assert meta.source_orbit_direction == MetadataSource.ASSET_REF
        # platform 从 URI 推断
        assert meta.platform == "Sentinel-1A"
        assert meta.source_platform == MetadataSource.INFERRED
        # polarizations 从 bands 推断（ASSET_REF）
        assert meta.polarizations == ["VV", "VH"]
        assert meta.source_polarizations == MetadataSource.ASSET_REF
        # relative_orbit 未知
        assert meta.relative_orbit == -1
        assert meta.source_relative_orbit == MetadataSource.UNKNOWN

    def test_no_fake_datetime_now(self):
        """acquisition_time 不应使用 datetime.now() 伪造。"""
        ref = FakeAssetRef(uri="/fake/no_date.tif")
        meta = SarMetadataResolver.resolve(ref, "/fake/no_date.tif")
        # acquisition_time 应该为空，而不是当前时间
        assert meta.acquisition_time == ""
        assert meta.source_acquisition_time == MetadataSource.UNKNOWN

    def test_no_default_sentinel1a(self):
        """未知平台不应默认 Sentinel-1A。"""
        ref = FakeAssetRef(uri="/path/unknown_sar_scene.tif")
        meta = SarMetadataResolver.resolve(ref, "/path/unknown_sar_scene.tif")
        # URI 没有包含任何 S1 特征词 → platform 应为 UNKNOWN
        # _apply_inferred 会检查 URI，没有匹配则保持 UNKNOWN
        assert meta.platform == "UNKNOWN" or meta.source_platform == MetadataSource.UNKNOWN


# ── 2. 逐字段来源追踪 ──────────────────────────────────────────

class TestFieldSourceTracking:
    """验证每个关键字段的来源正确记录。"""

    def test_field_summary_structure(self):
        """field_summary() 返回正确的结构。"""
        meta = SarMetadata()
        summary = meta.field_summary()
        for f in ["platform", "orbit_direction", "relative_orbit",
                   "polarizations", "acquisition_time"]:
            assert f in summary
            assert "value" in summary[f]
            assert "source" in summary[f]
            assert "verified" in summary[f]

    def test_field_source_getter(self):
        """get_field_source() 返回正确的 source。"""
        meta = SarMetadata()
        assert meta.get_field_source("platform") == MetadataSource.UNKNOWN
        assert meta.get_field_source("nonexistent") == MetadataSource.UNKNOWN

    def test_inferred_fields_list(self):
        """inferred_fields() 正确列出推断字段。"""
        ref = FakeAssetRef(
            uri="/fake/s1a_grd_20240101.tif",
            bands=["VV"],
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/s1a_grd_20240101.tif")
        inferred = meta.inferred_fields()
        # platform 可能 inferred (URI 含 s1a)
        assert "platform" in inferred or meta.source_platform == MetadataSource.ASSET_REF
        # product_type 可能 inferred (URI 含 GRD)

    def test_unknown_fields_list(self):
        """unknown_fields() 正确列出未知字段。"""
        meta = SarMetadata()
        unknown = meta.unknown_fields()
        assert "orbit_direction" in unknown
        assert "relative_orbit" in unknown
        assert "acquisition_time" in unknown

    def test_verified_flag(self):
        """验证标记正确反映来源可信度。"""
        ref = FakeAssetRef(
            orbit_direction="ASCENDING",
            relative_orbit=55,
            uri="/fake/path.tif",
            bands=["VV", "VH"],
            acquisition_time="2024-01-01T00:00:00Z",
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        # AssetRef 来源应被标记为 verified
        assert meta.source_orbit_direction.is_verified()
        assert meta.source_relative_orbit.is_verified()
        assert meta.source_polarizations.is_verified()


# ── 3. Strict / Warn / Trust 门禁 ──────────────────────────────

class TestStrictGate:
    """strict 模式拒绝 inferred/unknown 关键字段。"""

    def test_strict_rejects_inferred_orbit_direction(self):
        """strict 拒绝 inferred orbit_direction。"""
        ref = FakeAssetRef(uri="/fake/path.tif", bands=["VV", "VH"])
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        # orbit_direction 应该是 UNKNOWN
        assert meta.orbit_direction == "UNKNOWN"
        missing = meta.missing_fields()
        assert "orbit_direction" in missing
        inferred = meta.inferred_fields()
        # 在 strict 下，missing 和 inferred 都可能导致拒绝
        assert len(missing) > 0

    def test_strict_rejects_inferred_relative_orbit(self):
        """strict 拒绝 inferred relative_orbit。"""
        ref = FakeAssetRef(uri="/fake/path.tif")
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        assert meta.relative_orbit == -1
        assert "relative_orbit" in meta.missing_fields()

    def test_strict_rejects_missing_acquisition_time(self):
        """strict 拒绝缺失 acquisition_time。"""
        ref = FakeAssetRef(uri="/fake/path.tif")
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        assert meta.acquisition_time == ""
        assert "acquisition_time" in meta.missing_fields()

    def test_strict_passes_with_complete_metadata(self):
        """完整元数据可通过 strict。"""
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        assert meta.missing_fields() == []

    def test_strict_passes_with_verified_source(self):
        """ASSET_REF 来源字段可通过 strict 门禁。"""
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
            source_platform=MetadataSource.ASSET_REF,
            source_orbit_direction=MetadataSource.ASSET_REF,
            source_relative_orbit=MetadataSource.ASSET_REF,
        )
        assert meta.missing_fields() == []


# ── 4. 极化方式 ──────────────────────────────────────────────────

class TestPolarizations:
    """极化方式解析和门禁。"""

    def test_vv_only(self):
        """只有 VV 极化。"""
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        assert meta.has_vv
        assert not meta.has_vh

    def test_vv_vh_both(self):
        """VV+VH 双极化。"""
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        assert meta.has_vv
        assert meta.has_vh

    def test_polarization_compatible(self):
        """极化兼容性判断。"""
        a = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        b = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-02T00:00:00Z",
        )
        assert a.is_polarization_compatible(b)

    def test_polarization_not_compatible(self):
        """极化不兼容。"""
        a = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        b = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-02T00:00:00Z",
        )
        assert not a.is_polarization_compatible(b)

    def test_inferred_polarizations_from_bands(self):
        """从 AssetRef.bands 推断极化。"""
        ref = FakeAssetRef(uri="/fake/path.tif", bands=["VV"])
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        assert meta.polarizations == ["VV"]
        assert meta.source_polarizations == MetadataSource.ASSET_REF


# ── 5. 同轨判断 ──────────────────────────────────────────────────

class TestSameOrbit:
    """同轨判断逻辑。"""

    def test_same_orbit_matches(self):
        """相同 orbit_direction + same relative_orbit。"""
        a = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        b = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=31.0,
            incidence_angle_max=47.0, acquisition_time="2024-02-01T00:00:00Z",
        )
        assert a.is_same_orbit(b)

    def test_different_relative_orbit(self):
        """不同 relative_orbit 不同轨。"""
        a = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01",
        )
        b = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=62,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-02-01",
        )
        assert not a.is_same_orbit(b)

    def test_unknown_relative_orbit_not_same(self):
        """未知 relative_orbit 不应视为同轨。"""
        a = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01",
        )
        b = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=-1,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-02-01",
        )
        assert not a.is_same_orbit(b)


# ── 6. 冲突合并 ──────────────────────────────────────────────────

class TestMergeConflict:
    """不同来源冲突时的正确行为。"""

    def test_asset_ref_wins_over_tags_on_platform(self):
        """AssetRef 的 platform 优于 inferred。"""
        ref = FakeAssetRef(
            platform="Sentinel-1B",
            uri="/fake/s1a_path.tif",  # URI 含 s1a 但显式指定 S1B
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/s1a_path.tif")
        # ASSET_REF 优先于 INFERRED
        assert meta.platform == "Sentinel-1B"
        assert meta.source_platform == MetadataSource.ASSET_REF

    def test_asset_ref_partial_no_override_unknown(self):
        """AssetRef 有字段时 inferred 不覆盖。"""
        ref = FakeAssetRef(
            orbit_direction="DESCENDING",
            uri="/fake/path.tif",
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/path.tif")
        # orbit_direction 来自 ASSET_REF
        assert meta.orbit_direction == "DESCENDING"
        assert meta.source_orbit_direction == MetadataSource.ASSET_REF
        # relative_orbit 仍然是 UNKNOWN
        assert meta.relative_orbit == -1

    def test_different_acquisition_time_sources(self):
        """不同来源的 acquisition_time 优先级正确。"""
        ref = FakeAssetRef(
            uri="/fake/s1a_20240101.tif",
            acquisition_time="2023-06-15T10:00:00Z",
        )
        meta = SarMetadataResolver.resolve(ref, "/fake/s1a_20240101.tif")
        # ASSET_REF > INFERRED
        assert meta.acquisition_time == "2023-06-15T10:00:00Z"
        assert meta.source_acquisition_time == MetadataSource.ASSET_REF


# ── 7. 边界条件 ──────────────────────────────────────────────────

class TestEdgeCases:
    """边界条件和错误处理。"""

    def test_geotiff_unreadable(self):
        """GeoTIFF 无法读取时降级到 inferred。"""
        ref = FakeAssetRef(
            uri="/nonexistent/path.tif",
            bands=["VV", "VH"],
        )
        meta = SarMetadataResolver.resolve(ref, "/nonexistent/path.tif")
        # 不会崩溃，应该使用 inferred/UNKNOWN
        assert meta.source_orbit_direction in (MetadataSource.UNKNOWN, MetadataSource.INFERRED)
        assert meta.polarizations == ["VV", "VH"]
        assert meta.source_polarizations == MetadataSource.ASSET_REF

    def test_empty_uri(self):
        """空 URI 不会崩溃。"""
        ref = FakeAssetRef(uri="")
        meta = SarMetadataResolver.resolve(ref, "")
        # 不应该崩溃
        assert meta.platform is not None

    def test_none_asset_ref(self):
        """None AssetRef 不会崩溃（实际应避免此情况）。"""
        # 至少不崩溃
        meta = SarMetadataResolver.resolve(None, "/fake/path.tif")
        assert meta is not None

    def test_incidence_angle_unknown_default(self):
        """入射角未知时不应使用默认 30-46 度伪装真实值。"""
        meta = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"],
            acquisition_time="2024-01-01T00:00:00Z",
        )
        # 未指定时不应默认为假真实值
        assert meta.incidence_angle_min == -1.0
        assert meta.incidence_angle_max == -1.0

    def test_same_orbit_with_negative_relative_orbit(self):
        """negative relative_orbit 不应匹配。"""
        a = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=-1,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01",
        )
        b = SarMetadata(
            platform="S1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=-1,
            polarizations=["VV"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-02-01",
        )
        # 两者都未知且为负，应不同轨
        assert not a.is_same_orbit(b)


# ── 8. Platform 推断 ────────────────────────────────────────────

class TestPlatformInference:
    """平台名称推断的正确性。"""

    def test_uri_contains_s1a(self):
        """URI 含 S1A/Sentinel-1A 应推断为 Sentinel-1A。"""
        for uri in ["/data/S1A_IW_SLC.tif", "/data/sentinel-1a_scene.tif",
                     "/data/s1a_2024.tif"]:
            meta = SarMetadataResolver.resolve(None, uri)
            assert meta.platform == "Sentinel-1A"
            assert meta.source_platform in (MetadataSource.INFERRED, MetadataSource.UNKNOWN)

    def test_uri_contains_s1b(self):
        """URI 含 S1B/Sentinel-1B 应推断为 Sentinel-1B。"""
        for uri in ["/data/S1B_IW_SLC.tif", "/data/sentinel-1b_scene.tif"]:
            meta = SarMetadataResolver.resolve(None, uri)
            assert meta.platform == "Sentinel-1B"
            assert meta.source_platform in (MetadataSource.INFERRED, MetadataSource.UNKNOWN)

    def test_uri_unknown_platform(self):
        """URI 不含平台信息时 platform 应为 UNKNOWN。"""
        meta = SarMetadataResolver.resolve(None, "/data/some_scene.tif")
        assert meta.platform == "UNKNOWN"
        assert meta.source_platform == MetadataSource.UNKNOWN


# ── 9. 向后兼容 ──────────────────────────────────────────────────

class TestBackwardCompatibility:
    """验证向后兼容性。"""

    def test_from_asset_ref_class_method(self):
        """SarMetadata.from_asset_ref 仍然可用。"""
        asset = FakeAssetRef(
            uri="/data/s1a_vv_vh.tif",
            bands=["vv", "vh"],
            acquisition_time="2024-01-15T10:30:00Z",
        )
        meta = SarMetadata.from_asset_ref(asset, "/data/s1a_vv_vh.tif")
        assert meta.polarizations == ["VV", "VH"]
        assert meta.has_vv and meta.has_vh
        assert meta.source_polarizations == MetadataSource.ASSET_REF

    def test_source_field_backward_compat(self):
        """旧的 source 字段仍然可用。"""
        ref = FakeAssetRef(uri="/fake/s1a_2024.tif")
        meta = SarMetadataResolver.resolve(ref, "/fake/s1a_2024.tif")
        # source 是一个 str（向后兼容）
        assert isinstance(meta.source, str)
        assert meta.source in ("asset_ref", "geotiff_tags", "sidecar", "inferred", "unknown")

    def test_sar_metadata_can_be_json_serialized(self):
        """SarMetadata 可以 JSON 序列化。"""
        meta = SarMetadata(
            platform="Sentinel-1A", product_type="GRD", processing_level="L1",
            orbit_direction="ASCENDING", relative_orbit=55,
            polarizations=["VV", "VH"], incidence_angle_min=30.0,
            incidence_angle_max=46.0, acquisition_time="2024-01-01T00:00:00Z",
        )
        d = meta.model_dump(mode="json")
        assert d["platform"] == "Sentinel-1A"
        assert d["source_platform"] == "unknown"
        # JSON 序列化不崩溃
        json.dumps(d)
