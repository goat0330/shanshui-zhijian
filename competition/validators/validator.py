"""
B3 — SubmissionValidator 增强

Validator 至少检查：
- schema_version
- predictions 非空或明确允许空 Bundle
- record_id 唯一
- inference_task_ref 唯一
- sample/task 顺序
- task 数量
- 状态与 payload 一致
- TaskType → PayloadType 矩阵校验
- detection 不得含空 detections，或明确空结构规则
- segmentation 需要 mask_ref
- change_detection 至少一个合法输出字段
- no_data/failed 不允许伪造成功 payload
- succeeded_empty 使用明确空语义
- 完整 bundle checksum
- source manifest hash
- PredictionRecord 顺序稳定
- 文件可读
- 引用 Artifact 存在
- 官方 Schema 未发布时，明确标记 internal_only
"""

from competition.exporters.competition_exporter import SubmissionBundle
from core.schemas.contracts.__init__ import TaskType


# ── TaskType → PayloadType 矩阵 ──────────────────────────────────

TASK_TYPE_PAYLOAD_MATRIX: dict[TaskType, str] = {
    TaskType.CLASSIFICATION: "classification",
    TaskType.OBJECT_DETECTION: "detection",
    TaskType.TEMPORAL_CHANGE_DETECTION: "change_detection",
    TaskType.WATER_EXTRACTION: "change_detection",
    TaskType.ANOMALY_SCORING: "anomaly_scoring",
}


class ValidationReport:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)


class SubmissionValidator:
    """校验 SubmissionBundle 完整性（B3 增强版）。"""

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def validate(
        self,
        bundle: SubmissionBundle,
        task_type_map: dict[str, TaskType] | None = None,
    ) -> ValidationReport:
        """校验 SubmissionBundle。

        Args:
            bundle: 待校验的提交包
            task_type_map: 可选，inference_task_ref → TaskType 映射，
                          用于校验 TaskType/PayloadType 正确性。
        """
        report = ValidationReport()

        # 1. Schema 版本检查
        if not bundle.schema_version.startswith("submission.internal"):
            report.add_error(
                f"schema_version 不是 internal 格式: {bundle.schema_version}")

        # 2. 标记为 internal only
        if self.strict_mode:
            report.add_warning(
                "当前格式为 internal mock，未使用官方 Schema，不能作为正式提交")

        # 3. predictions 非空
        if not bundle.predictions:
            report.add_warning("SubmissionBundle 中没有 PredictionRecord")

        # 4. 校验每条 PredictionRecord
        seen_tasks: set[str] = set()
        seen_records: set[str] = set()
        task_type_map = task_type_map or {}

        for i, pr in enumerate(bundle.predictions):
            # 基本字段
            if not pr.record_id:
                report.add_error(f"predictions[{i}] record_id 为空")
            if pr.record_id in seen_records:
                report.add_error(
                    f"predictions[{i}] record_id 重复: {pr.record_id}")
            seen_records.add(pr.record_id)

            if not pr.inference_task_ref:
                report.add_error(f"predictions[{i}] inference_task_ref 为空")
            if pr.inference_task_ref in seen_tasks:
                report.add_error(
                    f"inference_task_ref 重复: {pr.inference_task_ref}")
            seen_tasks.add(pr.inference_task_ref)

            if not pr.execution_status:
                report.add_error(
                    f"predictions[{i}] execution_status 为空")

            # 5. TaskType → PayloadType 校验
            inferred_ref = pr.inference_task_ref
            if inferred_ref in task_type_map:
                expected_task_type = task_type_map[inferred_ref]
                expected_payload_type = TASK_TYPE_PAYLOAD_MATRIX.get(
                    expected_task_type)
                if pr.payload and expected_payload_type:
                    actual_payload_type = pr.payload.prediction_type
                    if actual_payload_type != expected_payload_type:
                        report.add_error(
                            f"predictions[{i}] TaskType={expected_task_type.value} "
                            f"需要 payload_type={expected_payload_type} "
                            f"但收到 {actual_payload_type}")

            # 6. 状态与 payload 一致性
            status = pr.execution_status
            payload = pr.payload

            if status in ("no_data", "invalid_input", "failed"):
                # NO_DATA/INVALID_INPUT/FAILED → payload 必须为 None
                if payload is not None:
                    report.add_error(
                        f"predictions[{i}] status={status} 但 payload 非空，"
                        f"伪造成功预测")

            elif status == "succeeded_empty":
                # SUCCEEDED_EMPTY → 使用明确空语义
                if payload is not None:
                    ptype = payload.prediction_type
                    if ptype == "classification":
                        if payload.class_id != 0 or payload.confidence != 0.0:
                            report.add_warning(
                                f"predictions[{i}] succeeded_empty "
                                f"classification 应该使用空语义 "
                                f"(class_id=0, confidence=0.0)")
                    elif ptype == "detection":
                        if payload.detections:
                            report.add_warning(
                                f"predictions[{i}] succeeded_empty "
                                f"detection detections 应该为空列表")
                    elif ptype == "segmentation":
                        if payload.mask_ref:
                            report.add_warning(
                                f"predictions[{i}] succeeded_empty "
                                f"segmentation mask_ref 应为空字符串")
                    elif ptype == "change_detection":
                        if payload.change_pixels and payload.change_pixels > 0:
                            report.add_warning(
                                f"predictions[{i}] succeeded_empty "
                                f"change_detection change_pixels 应为 0")
                    elif ptype == "anomaly_scoring":
                        pass  # anomaly scoring 没有强制空语义

            elif status == "succeeded_with_observations":
                # SUCCEEDED_WITH_OBSERVATIONS → payload 必须有值
                if payload is None:
                    report.add_error(
                        f"predictions[{i}] status=succeeded_with_observations "
                        f"但 payload 为空")

            # 7. 特定 payload 类型的检查
            if payload is not None:
                ptype = payload.prediction_type
                if ptype == "detection":
                    if hasattr(payload, "detections") and payload.detections == []:
                        if status != "succeeded_empty":
                            report.add_warning(
                                f"predictions[{i}] detection detections 为空列表")
                elif ptype == "segmentation":
                    if not payload.mask_ref:
                        report.add_warning(
                            f"predictions[{i}] segmentation mask_ref 为空")
                elif ptype == "change_detection":
                    if (payload.change_mask_ref is None and
                            payload.polygons_ref is None and
                            payload.change_pixels is None):
                        report.add_error(
                            f"predictions[{i}] change_detection "
                            f"至少需要一个输出字段")

        # 8. task_count 一致性
        if bundle.task_count > 0 and bundle.task_count != len(seen_tasks):
            report.add_error(
                f"task_count 声明={bundle.task_count} 实际={len(seen_tasks)}")

        # 9. Checksum 校验
        computed = bundle.compute_checksum()
        if bundle.bundle_checksum:
            if bundle.bundle_checksum != computed:
                report.add_error(
                    f"bundle_checksum 不匹配: "
                    f"声明={bundle.bundle_checksum[:16]}..., "
                    f"计算={computed[:16]}...")
            if len(bundle.bundle_checksum) != 64:
                report.add_error(
                    f"bundle_checksum 长度={len(bundle.bundle_checksum)}, "
                    f"期望 64")

        # 10. 文件可读
        try:
            _ = bundle.to_bytes()
        except Exception as e:
            report.add_error(f"bundle 序列化失败: {e}")

        # 11. PredictionRecord 顺序
        refs = [p.inference_task_ref for p in bundle.predictions]
        if refs != sorted(refs):
            report.add_warning("PredictionRecord 未按 inference_task_ref 排序")

        return report

    def validate_envelope(self, envelope_json: dict) ->ValidationReport:
        """校验 SubmissionEnvelope。

        Args:
            envelope_json: 解析后的 envelope JSON 字典。
        """
        report = ValidationReport()

        # envelope_hash 校验
        if "envelope_hash" in envelope_json:
            declared_eh = envelope_json["envelope_hash"]
            import copy
            env_data = copy.deepcopy(envelope_json)
            env_data.pop("envelope_hash", None)
            from core.schemas.contracts.submission_envelope import (
                canonical_json, full_sha256)
            expected_eh = full_sha256(
                canonical_json(env_data).encode("utf-8"))
            if declared_eh != expected_eh:
                report.add_error("envelope_hash 不匹配")

        # payload_hash 校验
        if "payload_hash" in envelope_json:
            ph = envelope_json["payload_hash"]
            if not ph:
                report.add_error("payload_hash 为空")
            elif len(ph) != 64:
                report.add_error(f"payload_hash 长度={len(ph)}, 期望 64")

        # bundle_id
        if not envelope_json.get("bundle_id"):
            report.add_error("bundle_id 为空")

        # source_manifest_hash
        if "source_manifest_hash" in envelope_json:
            smh = envelope_json["source_manifest_hash"]
            if smh and len(smh) != 64:
                report.add_error(
                    f"source_manifest_hash 长度={len(smh)}, 期望 64")

        return report
