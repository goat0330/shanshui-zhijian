"""
RS-01A — SarTemporalChangeTool

封装现有 Sentinel-1 SAR 双时相变化检测逻辑为 PerceptionTool。
不修改 run_pipeline.py，复用 pipeline/ 下的底层模块。
"""

import sys
from pathlib import Path
from datetime import datetime

# 确保能找到 pipeline 模块
ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

import numpy as np
from core.schemas.contracts import ExecutionStatus, TaskType, ObservationType, ScoreType, AssetRole
from core.schemas.contracts.task import InferenceTask, TaskSpec, RunContext
from core.schemas.contracts.perception import PerceptionResult, Observation, QualityReport
from core.protocols.perception_tool import PerceptionTool

# Pipeline 底层模块（不调用 run_pipeline.py 的 main()）
from pipeline.io.reader import read_geotiff
from pipeline.processing.preprocessor import reproject_to_target, resample_to_grid
from pipeline.models.baseline_water_sar import predict_vh as sar_water_predict
from pipeline.detection.change import detect_change
from pipeline.postprocessing.polygonize import polygonize_change_mask


class SarTemporalChangeTool(PerceptionTool):
    """
    Sentinel-1 SAR 双时相变化检测工具。

    输入:
        task: 包含 before/after 角色的 SAR asset 绑定
        spec: 任务规则（验证 input_slots）
        context: 运行配置（阈值、输出目录）

    输出:
        PerceptionResult（含 Observations 和 artifact_refs）
    """

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        result_id = f"pr-{task.task_id}"
        started_at = datetime.now().isoformat()

        # 1. 解析资产绑定
        assets = self._resolve_assets(task)
        if not assets:
            return PerceptionResult(
                perception_result_id=result_id,
                inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref,
                run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                quality_report=QualityReport(reasons=["missing_required_role: before/after"]),
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        # 2. 读取并预处理 SAR 数据
        try:
            sar_t1 = read_geotiff(assets["before"], bands=["vv", "vh"])
            sar_t2 = read_geotiff(assets["after"], bands=["vv", "vh"])
        except Exception as e:
            return PerceptionResult(
                perception_result_id=result_id,
                inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref,
                run_id=context.run_id,
                status=ExecutionStatus.FAILED,
                diagnostics={"error": f"读取 SAR 数据失败: {str(e)}"},
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        # 3. 重投影到统一 CRS
        sar_t1 = reproject_to_target(sar_t1)
        sar_t2 = reproject_to_target(sar_t2)

        # 对齐到同一网格
        ref = sar_t1
        if sar_t2.width != ref.width or sar_t2.height != ref.height:
            sar_t2 = resample_to_grid(sar_t2, ref)

        # 4. SAR 水体检测
        try:
            water_t1, thresh_t1 = sar_water_predict(sar_t1.array[sar_t1.bands.index("vh")])
            water_t2, thresh_t2 = sar_water_predict(sar_t2.array[sar_t2.bands.index("vh")])
        except Exception as e:
            return PerceptionResult(
                perception_result_id=result_id,
                inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref,
                run_id=context.run_id,
                status=ExecutionStatus.FAILED,
                diagnostics={"error": f"SAR 水体检测失败: {str(e)}"},
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        # 5. 变化检测
        change = detect_change(water_t1, water_t2)
        total_changed = change["stats"]["total_changed"]

        # 6. 多边形化
        transform = ref.transform
        crs = ref.crs
        features = polygonize_change_mask(
            change["change_mask"], transform, crs,
            min_area_m2=500, pixel_area_m2=100,
        )

        # 7. 构建 Observation
        observations = []
        if total_changed > 0:
            obs = Observation(
                observation_id=f"obs-{task.task_id}-sar-change",
                perception_result_ref=result_id,
                source_asset_refs=[assets["before"], assets["after"]],
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="sar_water_extent_change",
                score=min(1.0, total_changed / 10000.0),
                score_type=ScoreType.RULE_BASED,
                temporal={"start": "", "end": ""},
                quality={"change_pixels": total_changed},
                model_run_ref=context.run_id,
            )
            observations.append(obs)

        # 8. 构建 PerceptionResult
        status = ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS if observations else ExecutionStatus.SUCCEEDED_EMPTY
        artifact_refs = [f"water_change_mask_{task.task_id}.tif", f"anomaly_candidates_{task.task_id}.geojson"]

        result = PerceptionResult(
            perception_result_id=result_id,
            inference_task_ref=task.task_id,
            task_spec_ref=task.task_spec_ref,
            run_id=context.run_id,
            status=status,
            observations=observations,
            artifact_refs=artifact_refs,
            quality_report=QualityReport(
                valid_pixel_ratio=1.0,
                reasons=["sar_temporal_change_completed"],
            ),
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
        )
        return result

    def _resolve_assets(self, task: InferenceTask) -> dict[str, str]:
        """从 task.asset_bindings 解析 before/after 资产的 URI"""
        from core.schemas.contracts.asset import AssetRef

        # 构建 asset_id → AssetRef 映射（通过 manifest 解析时，资产信息需要外部传入）
        # 当前简化：直接从绑定中提取 asset_id，URI 由调用方处理
        assets = {}
        for binding in task.asset_bindings:
            if binding.role in (AssetRole.BEFORE, AssetRole.AFTER):
                assets[binding.role.value] = binding.asset_ref
        # 检查是否同时有 before 和 after
        if AssetRole.BEFORE.value not in assets or AssetRole.AFTER.value not in assets:
            return {}
        return assets
