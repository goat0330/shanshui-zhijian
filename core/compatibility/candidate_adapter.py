"""CandidateCompatibilityAdapter — v0.2→v0.3 migration + verification.

G0.3-A:
- schema_version auto-upgrade
- temporal_extent dict → TemporalExtent model
- candidate_type mapping
- auto candidate_track_id generation
- verify_v03() for post-migration validation
"""

from __future__ import annotations

import copy
from typing import Any

from core.schemas.contracts.candidate import (
    DetectionCandidate,
    CandidateLifecycle,
    compute_candidate_track_id,
)

SUPPORTED_VERSIONS = {"candidate.v0.2", "candidate.v0.3"}


def _make_track_id(v02: dict) -> str:
    """Generate candidate_track_id from v0.2 dict geometry."""
    return compute_candidate_track_id(
        representative_geometry=v02.get("geometry"),
        candidate_type=v02.get("candidate_type"),
    )


def _convert_temporal(v02_temporal: dict) -> dict:
    """Convert v0.2 {start, end} to v0.3 TemporalExtent (index/time split)."""
    result: dict = {"start_index": 0, "end_index": 0}
    if not v02_temporal:
        return result

    start = v02_temporal.get("start", 0)
    end = v02_temporal.get("end", 0)

    if isinstance(start, (int, float)):
        result["start_index"] = int(start)
    else:
        result["start_time"] = str(start)
        result["start_index"] = 0

    if isinstance(end, (int, float)):
        result["end_index"] = int(end)
    else:
        result["end_time"] = str(end)
        result["end_index"] = max(result["start_index"], 0)

    if result["end_index"] < result["start_index"]:
        result["end_index"] = result["start_index"]

    return result


def v02_to_v03(v02: dict) -> dict:
    """Convert a v0.2 candidate dict to v0.3-compatible dict.

    Handles:
    - schema_version upgrade
    - temporal_extent dict → TemporalExtent (index/time split)
    - candidate_type mapping (water_extent_change→water_gain)
    - lifecycle defaulting
    - score_type mapping
    - auto candidate_track_id generation
    - evidence_refs → tuple
    """
    result = copy.deepcopy(v02)
    result["schema_version"] = "candidate.v0.3"

    # ── candidate_track_id ──
    if "candidate_track_id" not in result:
        result["candidate_track_id"] = _make_track_id(v02)

    # ── temporal_extent ──
    if isinstance(result.get("temporal_extent"), dict):
        result["temporal_extent"] = _convert_temporal(result["temporal_extent"])

    # ── candidate_type mapping ──
    ct = result.get("candidate_type", "")
    if ct in ("water_extent_change", "water_gain_before"):
        result["candidate_type"] = "water_gain"
    elif ct in ("suspected_floating", "water_loss_before"):
        result["candidate_type"] = "sar_backscatter_anomaly"
    elif ct in ("water_extent_loss", "water_loss"):
        result["candidate_type"] = "water_loss"

    # ── lifecycle ──
    if "lifecycle" not in result or result["lifecycle"] is None:
        result["lifecycle"] = "proposed"

    # ── score_type ──
    if "score_type" in result:
        st = result["score_type"]
        if isinstance(st, str):
            if st in ("model_probability", "probability"):
                pass  # keep — handled by model
            elif st in ("rule_based", "raw_score"):
                result["score_type"] = "within_run_ranking"

    # ── evidence_refs → tuple ──
    if "evidence_refs" in result and not isinstance(result["evidence_refs"], tuple):
        result["evidence_refs"] = tuple(result["evidence_refs"])

    return result


class CandidateCompatibilityAdapter:
    """Compatibility adapter for DetectionCandidate versions."""

    SUPPORTED = SUPPORTED_VERSIONS

    @staticmethod
    def normalize(d: dict) -> dict:
        """Normalize to latest version (v0.3). Preserves unknown version error."""
        v = d.get("schema_version", "")
        if v not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported version: {v}")
        if v == "candidate.v0.2":
            return v02_to_v03(d)
        return d

    @staticmethod
    def to_detection_candidate(d: dict) -> DetectionCandidate:
        """Convert a dict (any version) to DetectionCandidate.v3."""
        normalized = CandidateCompatibilityAdapter.normalize(d)
        return DetectionCandidate(**normalized.get("candidate", normalized))

    @staticmethod
    def get_fixture_assets(d: dict) -> list:
        """Extract asset list from fixture dict."""
        return CandidateCompatibilityAdapter.normalize(d).get("assets", [])

    @staticmethod
    def get_modalities(d: dict) -> dict:
        """Extract modality info from fixture dict."""
        n = CandidateCompatibilityAdapter.normalize(d)
        return dict(
            modalities_expected=n.get("modalities_expected", []),
            modalities_present=n.get("modalities_present", []),
            modalities_missing=n.get("modalities_missing", []),
            missing_context_notes=n.get("missing_context_notes"),
        )

    @staticmethod
    def verify_v03(instance: DetectionCandidate) -> list[str]:
        """Verify a DetectionCandidate.v3 is well-formed. Returns issues list."""
        issues: list[str] = []
        if instance.schema_version != "candidate.v0.3":
            issues.append(f"Wrong schema_version: {instance.schema_version}")
        if not instance.candidate_track_id:
            issues.append("Missing candidate_track_id")
        if len(instance.candidate_id) != 64:
            issues.append(f"candidate_id not SHA256: {instance.candidate_id}")
        if instance.lifecycle == CandidateLifecycle.SUPPRESSED and not instance.suppression_reason:
            issues.append("Suppressed lifecycle missing suppression_reason")
        return issues
