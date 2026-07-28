"""CandidateCompatibilityAdapter — v0.2→v0.3 migration + verification.

RS-03 RC-02:
- schema_version: "rs-contract.v0.3" (unified across all contracts)
- temporal_extent: v0.2 {start: int, end: int} → v0.3 {"start": str, "end": str}
- evidence_refs kept as list[str] (not tuple)
- adapter uses model_validate() for strict field filtering
"""

from __future__ import annotations

import copy

from core.schemas.contracts.candidate import DetectionCandidate

SUPPORTED_VERSIONS = {"candidate.v0.2", "candidate.v0.3", "rs-contract.v0.2", "rs-contract.v0.3"}


def _convert_temporal(v02_temporal: dict) -> dict:
    """Convert v0.2 integer temporal_extent to v0.3 string temporal_extent.

    v0.2: {"start": 0, "end": 0}  (integers — indices)
    v0.3: {"start": "unknown", "end": "unknown"}  (strings — ISO time or unknown)
    """
    if not v02_temporal:
        return {"start": "unknown", "end": "unknown"}

    start = v02_temporal.get("start", 0)
    end = v02_temporal.get("end", 0)

    return {
        "start": "unknown" if isinstance(start, (int, float)) else str(start),
        "end": "unknown" if isinstance(end, (int, float)) else str(end),
    }


def _unwrap_v02(v02: dict) -> dict:
    """Extract the actual candidate dict from a v0.2 fixture wrapper.

    v0.2 fixtures have structure:
      {"schema_version": "...", "candidate": {...}, "observations": [...], ...}
    This function returns the inner "candidate" dict, or v02 itself if no wrapper.
    """
    inner = v02.get("candidate")
    if isinstance(inner, dict):
        return inner
    return v02


def v02_to_v03(v02: dict) -> dict:
    """Convert a v0.2 candidate dict to v0.3-compatible dict.

    Handles:
    - schema_version: "rs-contract.v0.3"
    - temporal_extent: {start: int, end: int} -> {"start": str, "end": str}
    - candidate_type: old names -> v0.3 names
    - evidence_refs: kept as list[str]
    - Removes v0.2-only fields not in DetectionCandidate v0.3
    """
    # Unwrap fixture wrapper (handle both flat and wrapped v0.2 dicts)
    src = _unwrap_v02(v02)

    # Start with only the fields that belong to DetectionCandidate v0.3
    result: dict = {}
    result["schema_version"] = "rs-contract.v0.3"

    # -- candidate_id --
    if "candidate_id" in src:
        result["candidate_id"] = src["candidate_id"]

    # -- observation_refs --
    if "observation_refs" in src:
        result["observation_refs"] = src["observation_refs"]

    # -- temporal_extent --
    te = src.get("temporal_extent")
    if te is not None and isinstance(te, dict):
        result["temporal_extent"] = _convert_temporal(te)
    else:
        result["temporal_extent"] = {"start": "unknown", "end": "unknown"}

    # -- candidate_type mapping --
    ct = src.get("candidate_type", "")
    if ct in ("water_extent_change", "water_gain"):
        result["candidate_type"] = "water_extent_change"
    elif ct in ("suspected_floating", "sar_backscatter_anomaly"):
        result["candidate_type"] = "suspected_floating"
    elif ct in ("water_extent_loss", "water_loss"):
        result["candidate_type"] = "water_extent_change"
    else:
        result["candidate_type"] = ct if ct else "unknown"

    # -- geometry --
    if "geometry" in src and src["geometry"] is not None:
        result["geometry"] = src["geometry"]

    # -- score --
    if "score" in src:
        result["score"] = src["score"]

    # -- quality_summary --
    qs = src.get("quality_summary")
    if qs is not None and isinstance(qs, dict):
        filtered_qs = {}
        if "mean_score" in qs:
            filtered_qs["mean_score"] = qs["mean_score"]
        elif "mean_confidence" in qs or "valid_pixel_ratio" in qs:
            filtered_qs["mean_score"] = qs.get("mean_confidence") or qs.get("valid_pixel_ratio", 0.0)
        if "n_observations" in qs:
            filtered_qs["n_observations"] = qs["n_observations"]
        if "area_consistency" in qs:
            filtered_qs["area_consistency"] = qs["area_consistency"]
        if "score_std" in qs:
            filtered_qs["score_std"] = qs["score_std"]
        if filtered_qs and "mean_score" in filtered_qs and "n_observations" in filtered_qs:
            result["quality_summary"] = filtered_qs

    # -- evidence_refs -> list[str] --
    if "evidence_refs" in src:
        refs = src["evidence_refs"]
        if isinstance(refs, (list, tuple)):
            result["evidence_refs"] = list(refs)

    # -- rule_version --
    if "rule_version" in src:
        result["rule_version"] = src["rule_version"]

    # -- coordinate_space (optional, v0.3+) --
    if "coordinate_space" in src:
        result["coordinate_space"] = src["coordinate_space"]

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
        if v in ("candidate.v0.2", "rs-contract.v0.2"):
            return v02_to_v03(d)
        # v0.3+: filter only valid fields via model_validate
        # Unwrap fixture wrapper if present
        raw = d.get("candidate", d)
        valid = DetectionCandidate.model_validate(raw)
        return valid.model_dump()

    @staticmethod
    def to_detection_candidate(d: dict) -> DetectionCandidate:
        """Convert a dict (any version) to DetectionCandidate.v3.

        Uses model_validate() for strict field filtering — v0.2-only fields
        are silently dropped.
        """
        normalized = CandidateCompatibilityAdapter.normalize(d)
        # normalized is already a valid v0.3 dict; use model_validate to construct
        return DetectionCandidate.model_validate(normalized)

    @staticmethod
    def get_fixture_assets(d: dict) -> list:
        """Extract asset list from fixture dict."""
        n = CandidateCompatibilityAdapter.normalize(d)
        # normalize with fixture wrapper — use original dict for auxiliary fields
        return d.get("assets", [])

    @staticmethod
    def get_modalities(d: dict) -> dict:
        """Extract modality info from fixture dict."""
        return dict(
            modalities_expected=d.get("modalities_expected", []),
            modalities_present=d.get("modalities_present", []),
            modalities_missing=d.get("modalities_missing", []),
            missing_context_notes=d.get("missing_context_notes"),
        )

    @staticmethod
    def verify_v03(instance: DetectionCandidate) -> list[str]:
        """Verify a DetectionCandidate.v3 is well-formed. Returns issues list."""
        issues: list[str] = []
        if instance.schema_version != "rs-contract.v0.3":
            issues.append(f"Wrong schema_version: {instance.schema_version}")
        if not instance.observation_refs:
            issues.append("Missing observation_refs reference")
        if instance.score < 0.0 or instance.score > 1.0:
            issues.append(f"Score out of range: {instance.score}")
        return issues
