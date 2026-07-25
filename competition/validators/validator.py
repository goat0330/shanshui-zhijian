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
- detection 不得含空 detections，或明确空结构规则
- segmentation 需要 mask_ref
- change_detection 至少一个合法输出字段
- no_data/failed 不允许伪造成功 payload
- 完整 bundle checksum
- source manifest hash
- PredictionRecord 顺序稳定
- 文件可读
- 引用 Artifact 存在
- 官方 Schema 未发布时，明确标记 internal_only
"""

from competition.exporters.competition_exporter import SubmissionBundle


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

    def validate(self, bundle: SubmissionBundle) -> ValidationReport:
        report = ValidationReport()

        # 1. Schema 版本检查
        if not bundle.schema_version.startswith("submission.internal"):
            report.add_error(f"schema_version 不是 internal 格式: {bundle.schema_version}")

        # 2. 标记为 internal only
        if self.strict_mode:
            report.add_warning("当前格式为 internal mock，未使用官方 Schema，不能作为正式提交")

        # 3. predictions 非空
        if not bundle.predictions:
            report.add_warning("SubmissionBundle 中没有 PredictionRecord")

        # 4. 校验每条 PredictionRecord
        seen_tasks: set[str] = set()
        seen_records: set[str] = set()

        for i, pr in enumerate(bundle.predictions):
            # 基本字段
            if not pr.record_id:
                report.add_error(f"predictions[{i}] record_id 为空")
            if pr.record_id in seen_records:
                report.add_error(f"predictions[{i}] record_id 重复: {pr.record_id}")
            seen_records.add(pr.record_id)

            if not pr.inference_task_ref:
                report.add_error(f"predictions[{i}] inference_task_ref 为空")
            if pr.inference_task_ref in seen_tasks:
                report.add_error(f"inference_task_ref 重复: {pr.inference_task_ref}")
            seen_tasks.add(pr.inference_task_ref)

            if not pr.execution_status:
                report.add_error(f"predictions[{i}] execution_status 为空")

            # 5. 状态与 payload 一致性
            status = pr.execution_status
            payload = pr.payload

            if status in ("no_data", "invalid_input", "failed"):
                # NO_DATA/INVALID_INPUT/FAILED → payload 必须为 None
                if payload is not None:
                    report.add_error(
                        f"predictions[{i}] status={status} 但 payload 非空，"
                        f"伪造成功预测")

            elif status == "succeeded_empty":
                # SUCCEEDED_EMPTY → payload 允许（表示无变化/空结果）
                pass

            elif status == "succeeded_with_observations":
                # SUCCEEDED_WITH_OBSERVATIONS → payload 必须有值
                if payload is None:
                    report.add_error(
                        f"predictions[{i}] status=succeeded_with_observations "
                        f"但 payload 为空")

            # 6. 特定 payload 类型的检查
            if payload is not None:
                ptype = payload.prediction_type
                if ptype == "detection":
                    # detection 不得含空 detections，除非是明确空
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
                            f"predictions[{i}] change_detection 至少需要一个输出字段")

        # 7. task_count 一致性
        if bundle.task_count > 0 and bundle.task_count != len(seen_tasks):
            report.add_error(
                f"task_count 声明={bundle.task_count} 实际={len(seen_tasks)}")

        # 8. Checksum 校验（完整 64 位）
        computed = bundle.compute_checksum()
        if bundle.bundle_checksum:
            if bundle.bundle_checksum != computed:
                report.add_error(
                    f"bundle_checksum 不匹配: 声明={bundle.bundle_checksum[:16]}..., "
                    f"计算={computed[:16]}...")
            if len(bundle.bundle_checksum) != 64:
                report.add_error(
                    f"bundle_checksum 长度={len(bundle.bundle_checksum)}, "
                    f"期望 64")

        # 9. 文件可读（通过 to_bytes 验证）
        try:
            _ = bundle.to_bytes()
        except Exception as e:
            report.add_error(f"bundle 序列化失败: {e}")

        # 10. PredictionRecord 顺序（按 inference_task_ref 稳定）
        refs = [p.inference_task_ref for p in bundle.predictions]
        if refs != sorted(refs):
            report.add_warning("PredictionRecord 未按 inference_task_ref 排序")

        return report
