"""
B3 — SubmissionEnvelope: byte-deterministic competition submission wrapper

Provides:
- SubmissionPayload (purely deterministic, no timestamps)
- SubmissionEnvelope (dynamic metadata + hash stamp chain)
- verify_file: comprehensive integrity checker
- Factory: from_bundle()
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from competition.exporters.competition_exporter import SubmissionBundle


__all__ = [
    "SubmissionPayload", "SubmissionEnvelope",
    "canonical_json", "full_sha256",
]


def canonical_json(obj: object) -> str:
    """Canonical JSON: sort_keys, UTF-8, no extra whitespace."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def full_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── SubmissionPayload (pure business content, no timestamps) ──────

class SubmissionPayload(BaseModel):
    """The deterministic competition submission payload.

    PURELY business content:
    - Contains ONLY the bundle (SubmissionBundle)
    - NO created_at, NO timestamps, NO environment info
    - Same bundle input -> byte-for-byte identical output
    """

    bundle: SubmissionBundle
    payload_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA256 of the canonical bundle bytes."""
        return full_sha256(self.bundle.to_bytes())

    def finalize(self) -> "SubmissionPayload":
        self.payload_hash = self.compute_hash()
        return self

    def to_bytes(self) -> bytes:
        """Canonical bytes WITHOUT payload_hash (for hash computation)."""
        raw = canonical_json({
            "bundle": json.loads(self.bundle.to_bytes()),
        })
        return raw.encode("utf-8")

    def to_bytes_complete(self) -> bytes:
        """Complete canonical bytes WITH payload_hash."""
        data = self.model_dump(mode="json")
        raw = canonical_json(data)
        return raw.encode("utf-8")

    def model_dump_json(self, *args, **kwargs) -> str:
        data = self.model_dump(mode="json", *args, **kwargs)
        return canonical_json(data)


# ── SubmissionEnvelope (dynamic metadata + hash chain) ────────────

class SubmissionEnvelope(BaseModel):
    """Outer envelope: dynamic metadata with self-verifying hash chain."""

    envelope_version: str = "submission.envelope.v0.1"
    bundle_id: str = Field(..., min_length=1)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    producer_version: str = ""
    source_manifest_hash: str = ""
    task_count: int = 0

    # Stamped hashes
    payload_hash: str = ""
    envelope_hash: str = ""

    def stamp(self, payload_hash: str) -> "SubmissionEnvelope":
        """Stamp the envelope with computed hashes and self-hash."""
        self.payload_hash = payload_hash
        self.envelope_hash = self._compute_envelope_hash()
        return self

    def _compute_envelope_hash(self) -> str:
        """Compute envelope hash (excludes envelope_hash itself)."""
        data = self.model_dump(mode="json", exclude={"envelope_hash"})
        raw = canonical_json(data)
        return full_sha256(raw.encode("utf-8"))

    def verify(self) -> bool:
        """Verify envelope integrity."""
        expected = self._compute_envelope_hash()
        return self.envelope_hash == expected

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    def model_dump_json(self, *args, **kwargs) -> str:
        data = self.model_dump(mode="json", *args, **kwargs)
        return canonical_json(data)


# ── Factory ───────────────────────────────────────────────────────

def from_bundle(
    bundle: SubmissionBundle,
    source_manifest_hash: str = "",
    producer_version: str = "",
) -> tuple[SubmissionPayload, SubmissionEnvelope]:
    """Factory: create a (payload, envelope) pair from a SubmissionBundle.

    The payload is purely deterministic (no timestamps).
    The envelope wraps it with dynamic metadata and hash chain.
    """
    # Create payload (pure business content)
    payload = SubmissionPayload(bundle=bundle)
    payload.finalize()

    # Create envelope
    envelope = SubmissionEnvelope(
        bundle_id=bundle.bundle_id,
        producer_version=producer_version,
        source_manifest_hash=source_manifest_hash,
        task_count=bundle.task_count,
    )
    envelope.stamp(payload.payload_hash)

    return payload, envelope


# ── Verification ──────────────────────────────────────────────────

def verify_file(path: str) -> dict:
    """Comprehensive file integrity verification.

    Checks:
    - Payload bytes integrity
    - payload_hash matches computed
    - envelope_hash matches computed
    - bundle_id consistency
    - task_count consistency
    - PredictionRecord order (sorted by inference_task_ref)
    - Artifact reference presence

    Returns:
        dict with keys: valid, errors, warnings, details
    """
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    try:
        content = Path(path).read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"无法读取或解析文件: {e}"],
            "warnings": [],
            "details": {},
        }

    # Determine if this is an envelope with embedded bundle
    payload_data = data.get("bundle", data)

    # Check bundle_id
    bundle_id = data.get("bundle_id", payload_data.get("bundle_id", ""))
    if not bundle_id:
        errors.append("bundle_id 为空")
    else:
        details["bundle_id"] = bundle_id

    # Check bundle content
    bundle = payload_data
    predictions = bundle.get("predictions", [])

    # Task count
    declared_task_count = bundle.get("task_count", 0)
    actual_unique_tasks = len({p.get("inference_task_ref", "") for p in predictions})
    if declared_task_count > 0 and declared_task_count != actual_unique_tasks:
        errors.append(
            f"task_count 声明={declared_task_count} 实际={actual_unique_tasks}")

    # PredictionRecord order
    refs = [p.get("inference_task_ref", "") for p in predictions]
    if refs != sorted(refs):
        warnings.append("PredictionRecord 未按 inference_task_ref 排序")

    # Artifact references
    for i, pr in enumerate(predictions):
        payload_inner = pr.get("payload")
        if payload_inner:
            ptype = payload_inner.get("prediction_type", "")
            if ptype == "segmentation":
                if not payload_inner.get("mask_ref"):
                    warnings.append(f"predictions[{i}] segmentation mask_ref 为空")
            elif ptype == "change_detection":
                mask = payload_inner.get("change_mask_ref")
                poly = payload_inner.get("polygons_ref")
                if not mask and not poly and payload_inner.get("change_pixels") is None:
                    errors.append(
                        f"predictions[{i}] change_detection 至少需要一个输出字段")

    # Payload hash verification
    if "payload_hash" in data:
        declared_ph = data["payload_hash"]
        # Recompute payload hash from bundle
        try:
            bundle_obj = payload_data
            bundle_bytes = canonical_json(bundle_obj).encode("utf-8")
            computed_ph = full_sha256(bundle_bytes)
            if declared_ph != computed_ph:
                errors.append(
                    f"payload_hash 不匹配: 声明={declared_ph[:16]}.. "
                    f"计算={computed_ph[:16]}..")
        except Exception as e:
            errors.append(f"payload_hash 重算失败: {e}")

    # Envelope hash verification
    if "envelope_hash" in data:
        declared_eh = data["envelope_hash"]
        try:
            import copy
            env_data = copy.deepcopy(data)
            env_data.pop("envelope_hash", None)
            envelope_bytes = canonical_json(env_data).encode("utf-8")
            computed_eh = full_sha256(envelope_bytes)
            if declared_eh != computed_eh:
                errors.append(
                    f"envelope_hash 不匹配: 声明={declared_eh[:16]}.. "
                    f"计算={computed_eh[:16]}..")
        except Exception as e:
            errors.append(f"envelope_hash 重算失败: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }
