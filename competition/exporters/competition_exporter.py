"""
RS-00 — SubmissionBundle + CompetitionExporter

使用 internal.v0.2 格式，不假设官方最终 Schema。
"""

import json
import hashlib
from datetime import datetime
from pydantic import BaseModel, Field
from core.schemas.contracts.prediction import PredictionRecord


class SubmissionBundle(BaseModel):
    """不可变的比赛提交包（内部格式）。"""
    schema_version: str = "submission.internal.v0.2"
    bundle_id: str = Field(..., min_length=1)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    predictions: list[PredictionRecord]
    bundle_checksum: str = ""

    def compute_checksum(self) -> str:
        raw = json.dumps([p.model_dump(mode="json") for p in self.predictions], sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class CompetitionExporter:
    """将 PredictionRecord 列表导出为 SubmissionBundle（内部格式）。"""

    def export(self, predictions: list[PredictionRecord], bundle_id: str | None = None) -> SubmissionBundle:
        if not bundle_id:
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            bundle_id = f"bundle-{ts}-{len(predictions)}tasks"

        bundle = SubmissionBundle(
            bundle_id=bundle_id,
            predictions=predictions,
        )
        bundle.bundle_checksum = bundle.compute_checksum()
        return bundle

    def export_to_file(self, predictions: list[PredictionRecord], output_path: str, bundle_id: str | None = None) -> str:
        bundle = self.export(predictions, bundle_id)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(bundle.model_dump_json(indent=2))
        return bundle.bundle_id
