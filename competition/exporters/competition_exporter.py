"""
RS-00 — SubmissionBundle + CompetitionExporter

使用 internal.v0.2 格式，不假设官方最终 Schema。

提供:
- SubmissionBundle: 不可变比赛提交包，含 byte-deterministic 序列化
- CompetitionExporter: 导出器
- verify_file: 文件完整性校验
"""

import hashlib
import json
from pathlib import Path
from pydantic import BaseModel, Field

from core.schemas.contracts.prediction import PredictionRecord


def canonical_json(obj: object) -> str:
    """Canonical JSON: sort_keys, UTF-8, no extra whitespace."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class SubmissionBundle(BaseModel):
    """不可变的比赛提交包（内部格式）。

    同一个 predictions 列表 → 完全相同的字节序列。
    """

    schema_version: str = "submission.internal.v0.2"
    bundle_id: str = Field(..., min_length=1)
    task_count: int = 0
    predictions: list[PredictionRecord]
    bundle_checksum: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-set task_count from predictions
        if "task_count" not in data or not data.get("task_count"):
            predictions = data.get("predictions", [])
            unique_tasks = len({p.inference_task_ref
                                for p in predictions})
            self.task_count = unique_tasks

    def compute_checksum(self) -> str:
        """Compute full SHA256 of canonical bundle bytes."""
        raw = self.to_bytes()
        return hashlib.sha256(raw).hexdigest()

    def to_bytes(self) -> bytes:
        """Canonical bytes: deterministic, sort_keys, no extra spaces.

        Predictions sorted by inference_task_ref for stable ordering.
        Same content in any input order → identical bytes.
        """
        # Sort by inference_task_ref for deterministic order
        sorted_preds = sorted(
            self.predictions,
            key=lambda p: p.inference_task_ref,
        )
        preds_data = [p.model_dump(mode="json") for p in sorted_preds]
        raw = canonical_json({
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "task_count": self.task_count,
            "predictions": preds_data,
        })
        return raw.encode("utf-8")

    def to_bytes_with_checksum(self) -> bytes:
        """Canonical bytes including bundle_checksum."""
        raw = self.model_dump_json()
        return raw.encode("utf-8")

    def model_dump_json(self, *args, **kwargs) -> str:
        data = self.model_dump(mode="json", *args, **kwargs)
        return canonical_json(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "SubmissionBundle":
        """从 JSON 文件加载 SubmissionBundle。"""
        p = Path(path)
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        return cls.model_validate(data)

    def save(self, path: str | Path) -> Path:
        """保存 bundle 到 JSON 文件。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def verify_file(cls, path: str | Path) -> dict:
        """文件完整性校验。

        Returns:
            dict with keys: valid, errors, warnings
        """
        errors: list[str] = []
        warnings: list[str] = []
        p = Path(path)

        try:
            bundle = cls.from_file(str(p))
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"无法加载 bundle 文件: {e}"],
                "warnings": [],
            }

        # Checksum
        if bundle.bundle_checksum:
            computed = bundle.compute_checksum()
            if bundle.bundle_checksum != computed:
                errors.append(
                    f"bundle_checksum 不匹配: "
                    f"声明={bundle.bundle_checksum[:16]}.. "
                    f"计算={computed[:16]}..")
            if len(bundle.bundle_checksum) != 64:
                errors.append(
                    f"bundle_checksum 长度={len(bundle.bundle_checksum)}, "
                    f"期望 64")
        else:
            errors.append("bundle_checksum 为空")

        # Task count
        unique_tasks = len({p.inference_task_ref
                            for p in bundle.predictions})
        if bundle.task_count > 0 and bundle.task_count != unique_tasks:
            errors.append(
                f"task_count 声明={bundle.task_count} 实际={unique_tasks}")

        # Order
        refs = [p.inference_task_ref for p in bundle.predictions]
        if refs != sorted(refs):
            warnings.append("PredictionRecord 未按 inference_task_ref 排序")

        # Record uniqueness
        seen_records = set()
        for i, pr in enumerate(bundle.predictions):
            if pr.record_id in seen_records:
                errors.append(f"predictions[{i}] record_id 重复: {pr.record_id}")
            seen_records.add(pr.record_id)

            if not pr.inference_task_ref:
                errors.append(f"predictions[{i}] inference_task_ref 为空")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }


class CompetitionExporter:
    """将 PredictionRecord 列表导出为 SubmissionBundle（内部格式）。"""

    def export(
        self,
        predictions: list[PredictionRecord],
        bundle_id: str | None = None,
        source_manifest_hash: str | None = None,
    ) -> SubmissionBundle:
        # Validate: no duplicate inference_task_ref
        seen_refs: set[str] = set()
        for pr in predictions:
            if pr.inference_task_ref in seen_refs:
                raise ValueError(
                    f"重复的 inference_task_ref: {pr.inference_task_ref}")
            seen_refs.add(pr.inference_task_ref)

        if not bundle_id:
            if source_manifest_hash:
                identity = source_manifest_hash
            else:
                prediction_data = [
                    p.model_dump(mode="json")
                    for p in sorted(
                        predictions,
                        key=lambda p: p.inference_task_ref,
                    )
                ]
                identity = hashlib.sha256(
                    canonical_json(prediction_data).encode("utf-8")
                ).hexdigest()
            bundle_id = f"bundle-{identity[:16]}-{len(predictions)}tasks"

        bundle = SubmissionBundle(
            bundle_id=bundle_id,
            predictions=predictions,
        )
        bundle.bundle_checksum = bundle.compute_checksum()
        return bundle

    def export_to_file(
        self,
        predictions: list[PredictionRecord],
        output_path: str,
        bundle_id: str | None = None,
        source_manifest_hash: str | None = None,
    ) -> str:
        bundle = self.export(predictions, bundle_id, source_manifest_hash)
        bundle.save(output_path)
        return bundle.bundle_id
