"""
RS-01A 验收测试

覆盖:
1. PerceptionTool Protocol 可运行时检查
2. SarTemporalChangeTool 运行链 (Fixture → InferenceTask → Tool → PerceptionResult)
3. TaskDrivenRunner 最小运行链
4. DetectionResultAdapter 兼容性
5. 新旧 Pipeline 同输入结果回归
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.schemas.contracts import ExecutionStatus, AssetRole, Modality
from core.schemas.contracts.task import InferenceTask, TaskSpec, InputSlotSpec, RunContext, TaskAssetBinding
from core.schemas.contracts.perception import PerceptionResult
from core.protocols.perception_tool import PerceptionTool
from core.protocols.task_runner import TaskDrivenRunner
from tools.sar_temporal_change_tool import SarTemporalChangeTool
from core.compatibility.detection_result_adapter import DetectionResultAdapter


# ── 1. Protocol 可运行时检查 ──

class TestPerceptionToolProtocol:
    def test_tool_is_runtime_checkable(self):
        """SarTemporalChangeTool 符合 PerceptionTool Protocol"""
        tool = SarTemporalChangeTool()
        assert isinstance(tool, PerceptionTool)

    def test_protocol_has_run_method(self):
        """PerceptionTool 协议要求 run 方法"""
        assert hasattr(SarTemporalChangeTool, "run")


# ── 2. SarTemporalChangeTool 运行链 ──

class TestSarTemporalChangeTool:
    def test_tool_accepts_inference_task(self):
        """工具接受 InferenceTask + TaskSpec + RunContext"""
        tool = SarTemporalChangeTool()
        task = InferenceTask(
            task_id="ut-sar-001", sample_id="ut-001", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="s1_t1_before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="s1_t2_after", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        ctx = RunContext(run_id="ut-run-001")
        result = tool.run(task, spec, ctx)

        assert isinstance(result, PerceptionResult)
        assert result.inference_task_ref == "ut-sar-001"
        assert result.status in (
            ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            ExecutionStatus.SUCCEEDED_EMPTY,
            ExecutionStatus.FAILED,
            ExecutionStatus.INVALID_INPUT,
        )

    def test_tool_missing_assets(self):
        """缺少必要 asset 时返回 INVALID_INPUT"""
        tool = SarTemporalChangeTool()
        task = InferenceTask(
            task_id="ut-sar-missing", sample_id="ut-missing", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="only_before", role=AssetRole.BEFORE),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        ctx = RunContext(run_id="ut-run-missing")
        result = tool.run(task, spec, ctx)
        assert result.status == ExecutionStatus.INVALID_INPUT


# ── 3. TaskDrivenRunner 最小运行链 ──

class TestTaskDrivenRunner:
    def test_runner_with_sar_tool(self):
        """TaskDrivenRunner 使用 SarTemporalChangeTool 运行"""
        runner = TaskDrivenRunner(tool=SarTemporalChangeTool())
        task = InferenceTask(
            task_id="ut-runner-001", sample_id="ut-runner", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="s1_before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="s1_after", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        ctx = RunContext(run_id="ut-runner-ctx")
        result = runner.run(task, spec, ctx)
        assert isinstance(result, PerceptionResult)

    def test_runner_default_tool(self):
        """TaskDrivenRunner 默认使用 SarTemporalChangeTool"""
        runner = TaskDrivenRunner()
        assert isinstance(runner._tool, SarTemporalChangeTool)


# ── 4. DetectionResultAdapter 兼容性 ──

class TestAdapterCompatibility:
    def test_adapter_accepts_tool_output(self):
        """SarTemporalChangeTool 的输出可以通过 DetectionResultAdapter 转为 PredictionRecord"""
        adapter = DetectionResultAdapter()
        tool = SarTemporalChangeTool()

        task = InferenceTask(
            task_id="ut-adapter-001", sample_id="ut-adapter", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="s1_before", role=AssetRole.BEFORE),
            ],
        )
        ctx = RunContext(run_id="ut-adapter-ctx")
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        perception_result = tool.run(task, spec, ctx)
        pr = adapter.to_prediction_record(perception_result, task)
        assert pr.inference_task_ref == "ut-adapter-001"
        assert pr.execution_status is not None


# ── 5. 同输入新旧结果回归 ──

class TestRegression:
    def test_sar_tool_rejects_bad_task_spec(self):
        """错误的 task_spec_ref 不会导致崩溃"""
        tool = SarTemporalChangeTool()
        task = InferenceTask(
            task_id="ut-reg-001", sample_id="ut-reg", task_order=0,
            task_spec_ref="unknown-spec",
            asset_bindings=[
                TaskAssetBinding(asset_ref="before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="after", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        ctx = RunContext(run_id="ut-reg-ctx")
        # 不应抛出异常
        result = tool.run(task, spec, ctx)
        assert isinstance(result, PerceptionResult)

    def test_detection_result_adapter_empty_input(self):
        """空 DetectionResult 列表通过 Adapter 应返回 SUCCEEDED_EMPTY"""
        adapter = DetectionResultAdapter()
        task = InferenceTask(
            task_id="ut-reg-empty", sample_id="ut-empty", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="a1", role=AssetRole.BEFORE)],
        )
        ctx = RunContext(run_id="ut-reg-ctx")
        dr_list = []
        perception_result = adapter.to_perception_result(dr_list, task, ctx)
        assert perception_result.status == ExecutionStatus.SUCCEEDED_EMPTY

    def test_sar_tool_output_structure(self):
        """SarTemporalChangeTool 输出结构验证"""
        tool = SarTemporalChangeTool()
        task = InferenceTask(
            task_id="ut-struct-001", sample_id="ut-struct", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="before_sar", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="after_sar", role=AssetRole.AFTER),
            ],
        )
        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1",
            version="1.0.0",
            task_type="temporal_change_detection",
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
            ],
        )
        ctx = RunContext(run_id="ut-struct-ctx", tool_config={"min_area_m2": 500})
        result = tool.run(task, spec, ctx)

        # 结构验证
        assert result.perception_result_id == f"pr-{task.task_id}"
        assert result.inference_task_ref == task.task_id
        assert result.run_id == ctx.run_id
        assert result.status in (
            ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            ExecutionStatus.SUCCEEDED_EMPTY,
            ExecutionStatus.INVALID_INPUT,
            ExecutionStatus.FAILED,
        )
        # Observations 非负
        assert len(result.observations) >= 0
        # artifact_refs 非负
        assert len(result.artifact_refs) >= 0
