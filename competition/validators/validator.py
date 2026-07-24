"""
RS-00 — Validator

校验 SubmissionBundle 的完整性。
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
    """校验 SubmissionBundle 的完整性。"""

    def validate(self, bundle: SubmissionBundle) -> ValidationReport:
        report = ValidationReport()

        # Schema 版本检查
        if not bundle.schema_version.startswith("submission.internal"):
            report.add_error(f"schema_version 不是 internal 格式: {bundle.schema_version}")

        # 预测记录数量
        if not bundle.predictions:
            report.add_warning("SubmissionBundle 中没有 PredictionRecord")

        # 校验每条 PredictionRecord
        seen_tasks = set()
        for i, pr in enumerate(bundle.predictions):
            if not pr.record_id:
                report.add_error(f"predictions[{i}] record_id 为空")
            if not pr.inference_task_ref:
                report.add_error(f"predictions[{i}] inference_task_ref 为空")
            if pr.inference_task_ref in seen_tasks:
                report.add_error(f"inference_task_ref 重复: {pr.inference_task_ref}")
            seen_tasks.add(pr.inference_task_ref)
            if not pr.execution_status:
                report.add_error(f"predictions[{i}] execution_status 为空")

        # Checksum 校验
        computed = bundle.compute_checksum()
        if bundle.bundle_checksum and bundle.bundle_checksum != computed:
            report.add_error(f"bundle_checksum 不匹配: 声明={bundle.bundle_checksum}, 计算={computed}")

        return report
