"""
B3 — Deterministic SubmissionBundle + CompetitionExporter

- 完整 64 位 SHA256
- Canonical JSON（sort_keys, ensure_ascii, 固定分隔符）
- bundle_id 基于内容哈希（非时间）
- created_at 不进入内容哈希
- 同一 PredictionRecord 重复构建字节一致
"""

import hashlib
import json
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from core.schemas.contracts.prediction import PredictionRecord


__all__ = ["SubmissionBundle", "CompetitionExporter"]


def _canonical_json(obj: object) -> str:
    """生成规范 JSON 字节（sort_keys, UTF-8, 无额外空格）。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _full_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SubmissionBundle(BaseModel):
    """不可变的比赛提交包（内部格式 v0.2 B3）。"""
    schema_version: str = "submission.internal.v0.2"
    build_version: str = "b3-1.0.0"
    bundle_id: str = Field(..., min_length=1)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    predictions: list[PredictionRecord]
    bundle_checksum: str = ""

    # 元数据
    task_count: int = 0
    prediction_count: int = 0
    source_manifest_hash: str = ""
    preflight_report: dict = Field(default_factory=dict)

    def compute_content_hash(self) -> str:
        """计算预测内容哈希（排除时间等动态字段）。"""
        ordered = sorted(self.predictions, key=lambda p: p.inference_task_ref)
        payloads = [p.model_dump(mode="json") for p in ordered]
        raw = _canonical_json({
            "schema_version": self.schema_version,
            "build_version": self.build_version,
            "predictions": payloads,
        })
        return _full_sha256(raw.encode("utf-8"))

    def compute_checksum(self) -> str:
        """完整 64 位 SHA256。"""
        return self.compute_content_hash()

    def model_dump_json(self, *args, **kwargs) -> str:
        """重写为规范 JSON 输出。"""
        data = self.model_dump(mode="json", *args, **kwargs)
        return _canonical_json(data)

    def to_bytes(self) -> bytes:
        """规范 JSON 字节。"""
        return self.model_dump_json().encode("utf-8")


class CompetitionExporter:
    """将 PredictionRecord 列表导出为确定性 SubmissionBundle。"""

    def export(
        self,
        predictions: list[PredictionRecord],
        source_manifest_hash: str = "",
        bundle_id: str | None = None,
    ) -> SubmissionBundle:
        """导出 SubmissionBundle（确定性构建）。"""
        # 按 inference_task_ref 排序以确保稳定
        sorted_preds = sorted(predictions, key=lambda p: p.inference_task_ref)

        # 校验重复 inference_task_ref
        seen_refs = set()
        for p in sorted_preds:
            if p.inference_task_ref in seen_refs:
                raise ValueError(f"重复 inference_task_ref: {p.inference_task_ref}")
            seen_refs.add(p.inference_task_ref)

        # 生成内容哈希（用于 bundle_id）
        content_hash = self._compute_prediction_hash(sorted_preds)

        if not bundle_id:
            bundle_id = f"bundle-{content_hash[:16]}"

        bundle = SubmissionBundle(
            bundle_id=bundle_id,
            predictions=sorted_preds,
            task_count=len(set(p.inference_task_ref for p in sorted_preds)),
            prediction_count=len(sorted_preds),
            source_manifest_hash=source_manifest_hash,
        )
        bundle.bundle_checksum = bundle.compute_checksum()
        return bundle

    def _compute_prediction_hash(self, predictions: list[PredictionRecord]) -> str:
        """计算 PredictionRecord 列表的内容哈希。"""
        payloads = [p.model_dump(mode="json") for p in predictions]
        raw = _canonical_json(payloads)
        return _full_sha256(raw.encode("utf-8"))

    def export_to_file(
        self,
        predictions: list[PredictionRecord],
        output_path: str,
        source_manifest_hash: str = "",
        bundle_id: str | None = None,
    ) -> str:
        """导出到文件，返回 bundle_id。"""
        bundle = self.export(predictions, source_manifest_hash, bundle_id)
        bytes_data = bundle.to_bytes()
        with open(output_path, "wb") as f:
            f.write(bytes_data)
        return bundle.bundle_id

    def verify_file(self, path: str) -> tuple[bool, str]:
        """验证文件完整性。"""
        try:
            content = open(path, "rb").read()
            data = json.loads(content)
            declared_checksum = data.get("bundle_checksum", "")
            # 重新计算校验和
            preds = [PredictionRecord(**p) for p in data.get("predictions", [])]
            bundle = self.export(preds)
            expected = bundle.bundle_checksum
            if declared_checksum == expected:
                return True, expected
            return False, f"声明={declared_checksum[:16]}..., 计算={expected[:16]}..."
        except Exception as e:
            return False, str(e)
