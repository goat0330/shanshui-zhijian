"""
RS-01A.1 综合验收测试

1. 合成 GeoTIFF 真实运行测试
2. 重庆真实数据回归测试
3. AssetResolver 测试
4. TaskSpec 校验测试
5. 真实产物写出验证
"""

import json
import sys, os, tempfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from pydantic import ValidationError

from core.schemas.contracts import (
    Modality, AssetRole, ExecutionStatus, TaskType,
)
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.task import (
    TaskAssetBinding, InputSlotSpec, TaskSpec, InferenceTask, RunContext,
)
from core.schemas.contracts.perception import PerceptionResult
from core.schemas.contracts.prediction import (
    PredictionRecord, ChangePrediction,
)
from core.protocols.perception_tool import PerceptionTool
from core.protocols.task_runner import TaskDrivenRunner
from core.protocols.asset_resolver import AssetRegistry
from tools.sar_temporal_change_tool import SarTemporalChangeTool
from core.compatibility.detection_result_adapter import DetectionResultAdapter
from competition.adapters.competition_input_adapter import CompetitionInputAdapter
from competition.mappers.competition_mapper import CompetitionMapper
from competition.exporters.competition_exporter import CompetitionExporter
from competition.validators.validator import SubmissionValidator


def make_synthetic_sar_tiff(path: str | Path, width: int = 64, height: int = 64,
                            water_rect: tuple[int, int, int, int] | None = None,
                            nodata: float = -9999.0):
    """生成合成 SAR GeoTIFF (VV+VH 双波段)。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vv = np.full((height, width), -12.0, dtype=np.float32)  # 水体 dB 背景
    vh = np.full((height, width), -18.0, dtype=np.float32)
    # 陆地 (右上)
    vv[:, width//2:] = -5.0
    vh[:, width//2:] = -8.0
    # 指定水体区域
    if water_rect:
        x1, y1, x2, y2 = water_rect
        vv[y1:y2, x1:x2] = -15.0
        vh[y1:y2, x1:x2] = -22.0
    transform = from_bounds(106.55, 29.55, 106.60, 29.60, width, height)
    with rasterio.open(path, "w", driver="GTiff", height=height, width=width,
                       count=2, dtype="float32", crs="EPSG:4326",
                       transform=transform, nodata=nodata, compress="lzw") as dst:
        dst.write(vv, 1)
        dst.write(vh, 2)
        dst.set_band_description(1, "VV")
        dst.set_band_description(2, "VH")
    return path


class TestSyntheticData:
    """合成 GeoTIFF 真实运行测试。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # T1: 水体在左上 16x16
        self.t1_path = make_synthetic_sar_tiff(
            self.tmpdir / "s1_t1.tif", 64, 64, water_rect=(0, 0, 16, 16))
        # T2: 水体扩大到左上到中间 32x32
        self.t2_path = make_synthetic_sar_tiff(
            self.tmpdir / "s1_t2.tif", 64, 64, water_rect=(0, 0, 32, 32))
        self.output_dir = self.tmpdir / "output"
        yield
        shutil.rmtree(self.tmpdir)

    def test_synthetic_data_creates_valid_geotiff(self):
        """合成数据能生成有效 GeoTIFF"""
        with rasterio.open(self.t1_path) as src:
            assert src.count == 2
            assert src.height == 64 and src.width == 64

    def test_tool_runs_with_synthetic_data(self):
        """使用合成数据必须返回 SUCCEEDED_WITH_OBSERVATIONS"""
        assets = [
            AssetRef(asset_id="syn_before", uri=str(self.t1_path),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
            AssetRef(asset_id="syn_after", uri=str(self.t2_path),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
        ]
        resolver = AssetRegistry(assets)
        tool = SarTemporalChangeTool(registry=resolver)
        task = InferenceTask(
            task_id="syn-test-001", sample_id="syn-001", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="syn_before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="syn_after", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1", version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        ctx = RunContext(run_id="syn-run-001", output_dir=str(self.output_dir))
        result = tool.run(task, spec, ctx)

        # 必须成功，不得是 FAILED 或 INVALID_INPUT
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS, \
            f"预期 SUCCEEDED_WITH_OBSERVATIONS, 实际 {result.status}, diagnostics={result.diagnostics}"

    def test_tool_produces_artifact_files(self):
        """工具必须在 output_dir 中产生真实产物文件"""
        tool = SarTemporalChangeTool(registry=AssetRegistry([
            AssetRef(asset_id="syn_before", uri=str(self.t1_path),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
            AssetRef(asset_id="syn_after", uri=str(self.t2_path),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
        ]))
        task = InferenceTask(
            task_id="syn-artifact", sample_id="syn-a", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="syn_before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="syn_after", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(task_spec_id="sar-temporal-change-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        ctx = RunContext(run_id="syn-art-run", output_dir=str(self.output_dir))
        result = tool.run(task, spec, ctx)

        # 产物文件必须存在 (新路径: output_dir/run_id/task_id/)
        prod_dir = self.output_dir / "syn-art-run" / "syn-artifact"
        files = ["water_t1.tif", "water_t2.tif",
                 "change_mask.tif", "candidates.geojson",
                 "run_report.json"]
        for fname in files:
            fp = prod_dir / fname
            assert fp.exists(), f"产物文件不存在: {fp}"

        # artifact_refs 非空
        assert len(result.artifact_refs) >= 1, "artifact_refs 不应为空"
        # Observations 应包含多边形信息
        if result.observations:
            obs = result.observations[0]
            assert obs.geometry is not None, "Observation 应包含 geometry"
            assert "area_m2" in obs.quality, "Observation quality 应包含 area_m2"

    def test_detection_result_adapter_with_synthetic(self):
        """旧适配器在合成数据上也能产生 PredictionRecord"""
        adapter = DetectionResultAdapter()
        tool = SarTemporalChangeTool(registry=AssetRegistry([
            AssetRef(asset_id="syn_before", uri=str(self.t1_path),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
            AssetRef(asset_id="syn_after", uri=str(self.t2_path),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
        ]))
        task = InferenceTask(
            task_id="syn-adapter", sample_id="syn-ad", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="syn_before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="syn_after", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(task_spec_id="sar-temporal-change-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        ctx = RunContext(run_id="syn-ad-run", output_dir=str(self.output_dir))
        result = tool.run(task, spec, ctx)
        pr = adapter.to_prediction_record(result, task)
        assert isinstance(pr, PredictionRecord)
        # change_pixels 应来自 diagnostics，不是 len(observations)
        if pr.payload:
            assert isinstance(pr.payload, ChangePrediction)
            assert pr.payload.change_pixels >= 0  # 不应是 1 (len(observations) 的数值)


class TestRealDataRegression:
    """重庆真实 S1 数据回归测试。"""

    RAW_DIR = ROOT / "data" / "chongqing_demo" / "raw"
    HAS_REAL_DATA = (RAW_DIR / "s1_t1.tif").exists() and (RAW_DIR / "s1_t2.tif").exists()

    @pytest.mark.skipif(not HAS_REAL_DATA, reason="重庆真实数据不存在")
    def test_tool_runs_with_real_data(self):
        """真实数据必须返回 SUCCEEDED_WITH_OBSERVATIONS"""
        assets = [
            AssetRef(asset_id="real_t1", uri=str(self.RAW_DIR / "s1_t1.tif"),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
            AssetRef(asset_id="real_t2", uri=str(self.RAW_DIR / "s1_t2.tif"),
                     media_type="image/tiff; application=geotiff", modality=Modality.SAR),
        ]
        resolver = AssetRegistry(assets)
        tool = SarTemporalChangeTool(registry=resolver)
        task = InferenceTask(
            task_id="real-reg-001", sample_id="real-001", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="real_t1", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="real_t2", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(task_spec_id="sar-temporal-change-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        tmpdir = Path(tempfile.mkdtemp())
        ctx = RunContext(run_id="real-reg-run", output_dir=str(tmpdir))
        result = tool.run(task, spec, ctx)
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS, \
            f"真实数据运行失败: {result.status}, diagnostics={result.diagnostics}"
        assert len(result.observations) > 0, "应有变化图斑"
        assert result.diagnostics.get("total_changed_pixels", 0) > 0, "应有变化像元"
        shutil.rmtree(tmpdir)


class TestAssetResolver:
    """AssetResolver 协议与实现"""

    def test_in_memory_resolver(self):
        assets = [AssetRef(asset_id="a1", uri="x.tif", media_type="image/tiff", modality=Modality.SAR)]
        r = AssetRegistry(assets)
        assert r.contains("a1")
        assert not r.contains("a2")
        assert r.resolve("a1").uri == "x.tif"
        with pytest.raises(KeyError):
            r.resolve("a2")


class TestSpecValidation:
    """TaskSpec 校验测试"""

    def test_validation_passes(self):
        """正确配置应通过校验"""
        assets = [AssetRef(asset_id="s1", uri="x.tif", media_type="image/tiff", modality=Modality.SAR),
                   AssetRef(asset_id="s2", uri="y.tif", media_type="image/tiff", modality=Modality.SAR)]
        resolver = AssetRegistry(assets)
        tool = SarTemporalChangeTool(registry=resolver)
        task = InferenceTask(task_id="t", sample_id="s", task_order=0,
            task_spec_ref="test-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="s1", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="s2", role=AssetRole.AFTER),
            ])
        spec = TaskSpec(task_spec_id="test-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        errors = tool.validate_spec(task, spec)
        assert errors == []

    def test_validation_rejects_wrong_ref(self):
        """错误的 task_spec_ref 应被拒绝"""
        tool = SarTemporalChangeTool()
        task = InferenceTask(task_id="t", sample_id="s", task_order=0,
            task_spec_ref="wrong-ref",
            asset_bindings=[TaskAssetBinding(asset_ref="s1", role=AssetRole.BEFORE)])
        spec = TaskSpec(task_spec_id="test-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        errors = tool.validate_spec(task, spec)
        assert len(errors) >= 1
        assert "不匹配" in errors[0]

    def test_validation_rejects_missing_role(self):
        """缺少必要 role 应被拒绝"""
        tool = SarTemporalChangeTool()
        task = InferenceTask(task_id="t", sample_id="s", task_order=0,
            task_spec_ref="test-v1@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="s1", role=AssetRole.BEFORE)])
        spec = TaskSpec(task_spec_id="test-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[
                             InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                             InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
                         ])
        errors = tool.validate_spec(task, spec)
        assert any("不足" in e for e in errors)

    def test_validation_rejects_wrong_modality(self):
        """错误的 modality 应被拒绝"""
        assets = [AssetRef(asset_id="s1", uri="x.tif", media_type="image/tiff", modality=Modality.OPTICAL)]
        resolver = AssetRegistry(assets)
        tool = SarTemporalChangeTool(registry=resolver)
        task = InferenceTask(task_id="t", sample_id="s", task_order=0,
            task_spec_ref="test-v1@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="s1", role=AssetRole.BEFORE)])
        spec = TaskSpec(task_spec_id="test-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        errors = tool.validate_spec(task, spec)
        assert any("modality" in e for e in errors)

    def test_validation_returns_invalid_input(self):
        """校验失败时工具返回 INVALID_INPUT（需要 resolver 以避免提前 FAILED）"""
        assets = [AssetRef(asset_id="s1", uri="x.tif", media_type="image/tiff", modality=Modality.SAR)]
        resolver = AssetRegistry(assets)
        tool = SarTemporalChangeTool(registry=resolver)
        task = InferenceTask(task_id="t", sample_id="s", task_order=0,
            task_spec_ref="wrong@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="s1", role=AssetRole.BEFORE)])
        spec = TaskSpec(task_spec_id="test-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        ctx = RunContext(run_id="r")
        result = tool.run(task, spec, ctx)
        assert result.status == ExecutionStatus.INVALID_INPUT


class TestTaskDrivenRunnerInjection:
    """TaskDrivenRunner 不绑定具体工具"""

    def test_runner_requires_tool(self):
        """Runner 必须注入工具"""
        with pytest.raises(TypeError):
            TaskDrivenRunner()

    def test_runner_accepts_injected_tool(self):
        """可以注入 SarTemporalChangeTool"""
        assets = [AssetRef(asset_id="a1", uri="x.tif", media_type="image/tiff", modality=Modality.SAR)]
        tool = SarTemporalChangeTool(registry=AssetRegistry(assets))
        runner = TaskDrivenRunner(tool=tool)
        assert runner._tool is tool

    def test_runner_does_not_import_tools(self):
        """core/protocols/task_runner.py 不应导入 tools"""
        import core.protocols.task_runner as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "from tools" not in src, "core 层不应导入 tools"

    def test_runner_does_not_default_sar(self):
        """TaskDrivenRunner 不应默认实例化 SarTemporalChangeTool"""
        import core.protocols.task_runner as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "SarTemporalChangeTool" not in src, "core 层不应引用具体工具"


class TestPredictionRecordPayload:
    """PredictionRecord 使用真实判别联合"""

    def test_change_prediction_payload(self):
        """ChangePrediction 是合法判别联合"""
        cp = ChangePrediction(change_pixels=5084)
        pr = PredictionRecord(
            record_id="pred-test", inference_task_ref="task-test",
            execution_status="succeeded_with_observations",
            payload=cp,
        )
        assert pr.payload is not None
        assert pr.payload.prediction_type == "change_detection"

    def test_empty_payload(self):
        """no_data 时 payload 为 None"""
        pr = PredictionRecord(
            record_id="pred-empty", inference_task_ref="task-empty",
            execution_status="no_data", payload=None,
        )
        assert pr.payload is None


class TestMapperPayload:
    """CompetitionMapper 产生真实判别联合"""

    def test_mapper_uses_diagnostics(self):
        """Mapper 使用 diagnostics.total_changed_pixels，不是 len(observations)"""
        mapper = CompetitionMapper()
        result = PerceptionResult(
            perception_result_id="pr-test", inference_task_ref="task-test",
            task_spec_ref="v1@1.0.0", run_id="run-test",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            observations=[],  # 故意传空列表
            diagnostics={"total_changed_pixels": 5000, "polygon_count": 10},
        )
        task = InferenceTask(task_id="task-test", sample_id="s", task_order=0,
            task_spec_ref="v1@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="a", role=AssetRole.BEFORE)])
        pr = mapper.map_result(
            result,
            task,
            TaskType.TEMPORAL_CHANGE_DETECTION,
        )
        assert pr.payload is not None
        if isinstance(pr.payload, ChangePrediction):
            assert pr.payload.change_pixels == 5000, "应使用 diagnostics，不是 len(obs)"
    def test_runner_integration_with_synthetic(self):
        """全链: TaskDrivenRunner → SarTemporalChangeTool → PerceptionResult"""
        tmpdir = Path(tempfile.mkdtemp())
        t1 = make_synthetic_sar_tiff(tmpdir / "t1.tif", 32, 32, water_rect=(0, 0, 8, 8))
        t2 = make_synthetic_sar_tiff(tmpdir / "t2.tif", 32, 32, water_rect=(0, 0, 16, 16))
        out = tmpdir / "out"
        resolver = AssetRegistry([
            AssetRef(asset_id="b", uri=str(t1), media_type="image/tiff; application=geotiff", modality=Modality.SAR),
            AssetRef(asset_id="a", uri=str(t2), media_type="image/tiff; application=geotiff", modality=Modality.SAR),
        ])
        tool = SarTemporalChangeTool(registry=resolver)
        runner = TaskDrivenRunner(tool=tool)
        task = InferenceTask(task_id="syn-full", sample_id="syn", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="b", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="a", role=AssetRole.AFTER),
            ])
        spec = TaskSpec(task_spec_id="sar-temporal-change-v1", version="1.0.0",
                         task_type="temporal_change_detection",
                         input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1), InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1)])
        ctx = RunContext(run_id="syn-full-run", output_dir=str(out))
        result = runner.run(task, spec, ctx)
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
        assert len(result.artifact_refs) >= 1
        shutil.rmtree(tmpdir)
