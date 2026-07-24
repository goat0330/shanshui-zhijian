"""
RS-00 A1 验收测试

验收标准：
1. Pydantic v2 严格校验；
2. 四类 Fixture 中的任务输入可以解析；
3. 错误 modality/role、数量和空间元数据能够被拒绝；
4. JSON Schema 可以稳定导出。
"""

import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.schemas.contracts import Modality, AssetRole, SpatialReliability
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.task import (
    TaskAssetBinding,
    InputSlotSpec,
    TaskSpec,
    InferenceTask,
    RunContext,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "competition" / "fixtures"


# ── 辅助函数 ──────────────────────────────────────────────────────

def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 1. 基本 Pydantic 校验 ────────────────────────────────────────

class TestPydanticValidation:
    def test_asset_ref_minimal(self):
        """最小 AssetRef 必须通过"""
        a = AssetRef(asset_id="a1", uri="data/x.tif", media_type="image/tiff", modality=Modality.OPTICAL)
        assert a.asset_id == "a1"

    def test_asset_ref_with_spatial(self):
        """带空间元数据的 AssetRef"""
        a = AssetRef(
            asset_id="s1_t1", uri="data/s1.tif", media_type="image/tiff",
            modality=Modality.SAR,
            spatial=SpatialMetadata(reliability=SpatialReliability.GEOREFERENCED, crs="EPSG:4326"),
        )
        assert a.spatial.reliability == SpatialReliability.GEOREFERENCED

    def test_asset_ref_bad_crs(self):
        """CRS 必须使用 EPSG: 格式"""
        with pytest.raises(ValidationError, match="CRS"):
            AssetRef(asset_id="a1", uri="x.tif", media_type="image/tiff", modality=Modality.OPTICAL,
                     spatial=SpatialMetadata(reliability=SpatialReliability.GEOREFERENCED, crs="WGS84"))

    def test_task_asset_binding(self):
        """TaskAssetBinding 最基本的绑定"""
        b = TaskAssetBinding(asset_ref="s1_t1", role=AssetRole.BEFORE)
        assert b.asset_ref == "s1_t1"
        assert b.role == AssetRole.BEFORE

    def test_task_asset_binding_with_index(self):
        """带 sequence_index 的绑定"""
        b = TaskAssetBinding(asset_ref="s2_t1", role=AssetRole.OPTICAL_SUPPORT, sequence_index=0)
        assert b.sequence_index == 0

    def test_input_slot_spec(self):
        """InputSlotSpec 定义"""
        s = InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1)
        assert s.min_items == 1

    def test_input_slot_spec_max_lt_min(self):
        """max_items < min_items 应该被拒绝"""
        with pytest.raises(ValidationError, match="max_items"):
            InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=2, max_items=1)

    def test_task_spec(self):
        """TaskSpec 完整定义"""
        ts = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        fp = ts.compute_fingerprint()
        assert fp
        assert len(fp) == 16

    def test_inference_task(self):
        """InferenceTask 完整定义"""
        it = InferenceTask(
            task_id="task-cq-001", sample_id="cq-001", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="s1_t1", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="s1_t2", role=AssetRole.AFTER),
            ],
        )
        assert it.task_order == 0  # 0-based

    def test_inference_task_no_bindings(self):
        """没有 asset_bindings 应被拒绝"""
        with pytest.raises(ValidationError):
            InferenceTask(
                task_id="task-x", sample_id="x", task_order=0,
                task_spec_ref="spec", asset_bindings=[],
            )

    def test_run_context_fingerprint(self):
        """RunContext 手动计算 run_fingerprint"""
        rc = RunContext(run_id="run-001")
        fp = rc.compute_fingerprint()
        assert fp
        assert len(fp) == 16


# ── 2. Fixture 解析测试 ───────────────────────────────────────────

class TestFixtureParsing:
    def test_whole_scene(self):
        """整景 GeoTIFF Fixture 解析"""
        fix = load_fixture("whole_scene.json")
        for a in fix["assets"]:
            ar = AssetRef(**a)
            assert ar.modality == Modality.OPTICAL
        it = InferenceTask(**fix["inference_task"])
        assert it.task_order == 0
        assert it.asset_bindings[0].role == AssetRole.CURRENT

    def test_png_tile(self):
        """PNG 切片 Fixture 解析"""
        fix = load_fixture("png_tile.json")
        assets = {a["asset_id"]: AssetRef(**a) for a in fix["assets"]}
        assert assets["tile_001"].spatial.reliability == SpatialReliability.PIXEL_ONLY
        assert assets["tile_001_crs"].modality == Modality.METADATA
        it = InferenceTask(**fix["inference_task"])
        bindings = {b.asset_ref: b.role for b in it.asset_bindings}
        assert bindings["tile_001_crs"] == AssetRole.SPATIAL_METADATA

    def test_t1_t2_pair(self):
        """T1/T2 配对 Fixture 解析"""
        fix = load_fixture("t1_t2_pair.json")
        it = InferenceTask(**fix["inference_task"])
        roles = {b.asset_ref: b.role for b in it.asset_bindings}
        assert roles["s2_t1"] == AssetRole.BEFORE
        assert roles["s2_t2"] == AssetRole.AFTER

    def test_multi_asset(self):
        """S1+S2 多资产 Fixture 解析"""
        fix = load_fixture("multi_asset.json")
        it = InferenceTask(**fix["inference_task"])
        roles = {b.asset_ref: b.role for b in it.asset_bindings}
        assert roles["s1_t1"] == AssetRole.BEFORE
        assert roles["s1_t2"] == AssetRole.AFTER
        assert roles["s2_t1"] == AssetRole.OPTICAL_SUPPORT
        assert roles["dem"] == AssetRole.AUXILIARY

    def test_all_four_fixtures(self):
        """四类 Fixture 全部解析"""
        for name in ["whole_scene.json", "png_tile.json", "t1_t2_pair.json", "multi_asset.json"]:
            fix = load_fixture(name)
            for a in fix["assets"]:
                AssetRef(**a)
            InferenceTask(**fix["inference_task"])


# ── 3. 错误拒绝测试 ───────────────────────────────────────────────

class TestRejection:
    def test_bad_modality(self):
        """错误的 modality 应被拒绝"""
        with pytest.raises(ValidationError):
            AssetRef(asset_id="a1", uri="x.tif", media_type="image/tiff", modality="sentinel")

    def test_bad_role(self):
        """错误的 role 应被拒绝"""
        with pytest.raises(ValidationError):
            TaskAssetBinding(asset_ref="x", role="invalid_role")

    def test_negative_task_order(self):
        """task_order 不能为负数"""
        with pytest.raises(ValidationError):
            InferenceTask(
                task_id="t", sample_id="s", task_order=-1,
                task_spec_ref="spec",
                asset_bindings=[TaskAssetBinding(asset_ref="a", role=AssetRole.BEFORE)],
            )

    def test_empty_asset_id(self):
        """asset_id 不能为空"""
        with pytest.raises(ValidationError):
            AssetRef(asset_id="", uri="x.tif", media_type="image/tiff", modality=Modality.OPTICAL)


# ── 4. JSON Schema 导出测试 ──────────────────────────────────────

class TestJsonSchema:
    def test_asset_ref_schema(self):
        """AssetRef 的 JSON Schema 可以稳定导出"""
        schema = AssetRef.model_json_schema()
        assert "properties" in schema
        assert "asset_id" in schema["properties"]
        assert schema["properties"]["asset_id"]["minLength"] == 1

    def test_inference_task_schema(self):
        """InferenceTask 的 JSON Schema 可以稳定导出"""
        schema = InferenceTask.model_json_schema() 
        assert "properties" in schema
        assert "asset_bindings" in schema["properties"]

    def test_run_context_schema(self):
        """RunContext 的 JSON Schema 可以稳定导出"""
        schema = RunContext.model_json_schema()
        assert "properties" in schema
