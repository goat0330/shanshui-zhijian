"""Cycle 3.1: Candidate schema validation tests — semantic_label, area_m2, multi-polygon, timestamps."""

import json

import pytest
from pydantic import ValidationError

from core.schemas.contracts.candidate import (
    DetectionCandidate,
    CandidateQualitySummary,
    EvidenceRef,
)
from core.schemas.contracts.perception import Observation


# ── DetectionCandidate semantic_label ─────────────────────────────────────

class TestDetectionCandidateSemanticLabel:
    def test_water_increase(self):
        dc = DetectionCandidate(
            candidate_id="test-001",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            semantic_label="water_increase",
            score=0.85,
            rule_version="v1",
        )
        assert dc.semantic_label == "water_increase"

    def test_water_decrease(self):
        dc = DetectionCandidate(
            candidate_id="test-002",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            semantic_label="water_decrease",
            score=0.65,
            rule_version="v1",
        )
        assert dc.semantic_label == "water_decrease"

    def test_other_label(self):
        dc = DetectionCandidate(
            candidate_id="test-003",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            semantic_label="other",
            score=0.5,
            rule_version="v1",
        )
        assert dc.semantic_label == "other"

    def test_semantic_label_serialization(self):
        dc = DetectionCandidate(
            candidate_id="test-004",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            semantic_label="water_increase",
            score=0.9,
            rule_version="v1",
        )
        data = json.loads(dc.model_dump_json())
        assert data["semantic_label"] == "water_increase"
        dc2 = DetectionCandidate.model_validate(data)
        assert dc2.semantic_label == "water_increase"

    def test_semantic_label_optional(self):
        dc = DetectionCandidate(
            candidate_id="test-005",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.9,
            rule_version="v1",
        )
        assert dc.semantic_label is None


# ── DetectionCandidate area_m2 ────────────────────────────────────────────

class TestDetectionCandidateArea:
    def test_area_m2_positive(self):
        dc = DetectionCandidate(
            candidate_id="test-area-1",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            area_m2=5000.0,
            score=0.8,
            rule_version="v1",
        )
        assert dc.area_m2 == 5000.0

    def test_area_m2_serialization(self):
        dc = DetectionCandidate(
            candidate_id="test-area-2",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            area_m2=12345.67,
            score=0.8,
            rule_version="v1",
        )
        data = json.loads(dc.model_dump_json())
        assert data["area_m2"] == 12345.67

    def test_area_m2_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            DetectionCandidate(
                candidate_id="test-area-bad",
                observation_refs=["obs-1"],
                temporal_extent={"start": "2026-01", "end": "2026-06"},
                candidate_type="water_extent_change",
                area_m2=-100.0,
                score=0.8,
                rule_version="v1",
            )


# ── Multi-Polygon Geometry ────────────────────────────────────────────────

class TestDetectionCandidateMultiPolygon:
    def test_multipolygon_geometry(self):
        dc = DetectionCandidate(
            candidate_id="test-mp-1",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            geometry={
                "type": "MultiPolygon",
                "coordinates": [
                    [[[106.55, 29.55], [106.56, 29.55], [106.56, 29.56], [106.55, 29.56], [106.55, 29.55]]],
                    [[[106.57, 29.57], [106.58, 29.57], [106.58, 29.58], [106.57, 29.58], [106.57, 29.57]]],
                ],
            },
            score=0.75,
            rule_version="v1",
        )
        assert dc.geometry["type"] == "MultiPolygon"
        assert len(dc.geometry["coordinates"]) == 2

    def test_single_polygon_geometry(self):
        dc = DetectionCandidate(
            candidate_id="test-sp-1",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            geometry={
                "type": "Polygon",
                "coordinates": [[[106.55, 29.55], [106.56, 29.55], [106.56, 29.56], [106.55, 29.56], [106.55, 29.55]]],
            },
            score=0.7,
            rule_version="v1",
        )
        assert dc.geometry["type"] == "Polygon"


# ── Temporal / Timestamps ─────────────────────────────────────────────────

class TestDetectionCandidateTemporal:
    def test_temporal_extent_real_dates(self):
        dc = DetectionCandidate(
            candidate_id="test-time-1",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-05-15T00:00:00Z", "end": "2026-06-30T23:59:59Z"},
            candidate_type="water_extent_change",
            score=0.85,
            rule_version="v1",
        )
        assert "2026-05-15" in dc.temporal_extent["start"]
        assert "2026-06-30" in dc.temporal_extent["end"]

    def test_temporal_extent_serialization(self):
        dc = DetectionCandidate(
            candidate_id="test-time-2",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-05-15T00:00:00Z", "end": "2026-06-30T23:59:59Z"},
            candidate_type="water_extent_change",
            score=0.85,
            rule_version="v1",
        )
        data = json.loads(dc.model_dump_json())
        assert data["temporal_extent"]["start"] == "2026-05-15T00:00:00Z"


# ── Evidence Refs ─────────────────────────────────────────────────────────

class TestDetectionCandidateEvidence:
    def test_evidence_refs_include_outputs(self):
        dc = DetectionCandidate(
            candidate_id="test-ev-1",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            evidence_refs=[
                "change_mask.tif",
                "change_polygons.geojson",
                "water_prob_t1.tif",
            ],
            score=0.8,
            rule_version="v1",
        )
        assert len(dc.evidence_refs) >= 2
        assert any("change_mask" in r for r in dc.evidence_refs)

    def test_evidence_refs_default_empty(self):
        dc = DetectionCandidate(
            candidate_id="test-ev-2",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.8,
            rule_version="v1",
        )
        assert dc.evidence_refs == []


# ── QualitySummary ────────────────────────────────────────────────────────

class TestCandidateQualitySummary:
    def test_quality_summary_basic(self):
        qs = CandidateQualitySummary(mean_score=0.5, n_observations=100)
        assert qs.mean_score == 0.5
        assert qs.n_observations == 100
        assert qs.area_consistency is None

    def test_quality_summary_full(self):
        qs = CandidateQualitySummary(
            mean_score=0.75, n_observations=200,
            area_consistency=0.9, score_std=0.1,
        )
        assert qs.area_consistency == 0.9
        assert qs.score_std == 0.1

    def test_quality_summary_score_range(self):
        with pytest.raises(ValidationError):
            CandidateQualitySummary(mean_score=1.5, n_observations=10)
        with pytest.raises(ValidationError):
            CandidateQualitySummary(mean_score=-0.1, n_observations=10)

    def test_quality_summary_low_observations(self):
        with pytest.raises(ValidationError):
            CandidateQualitySummary(mean_score=0.5, n_observations=0)


# ── Observation with real temporal ────────────────────────────────────────

class TestObservationWithTemporal:
    def test_observation_real_temporal(self):
        obs = Observation(
            observation_id="obs-t1-0000",
            perception_result_ref="run-test",
            source_asset_refs=["s2_t1"],
            source_task_type="anomaly_scoring",
            observation_type="anomaly_score",
            label="water",
            score=0.9,
            score_type="model_probability",
            geometry={"type": "Point", "coordinates": [106.5, 29.5]},
            temporal={"start": "2026-05-15T00:00:00Z", "end": "2026-05-31T23:59:59Z"},
            model_run_ref="run-test",
            coordinate_space="geographic",
        )
        assert obs.temporal["start"] == "2026-05-15T00:00:00Z"
        assert obs.temporal["end"] == "2026-05-31T23:59:59Z"

    def test_observation_geometry_crs(self):
        obs = Observation(
            observation_id="obs-geo-1",
            perception_result_ref="r1",
            source_asset_refs=["s2_t1"],
            source_task_type="anomaly_scoring",
            observation_type="anomaly_score",
            label="water",
            score=0.8,
            score_type="model_probability",
            geometry={"type": "Point", "coordinates": [106.5, 29.5]},
            geometry_crs="EPSG:4326",
            model_run_ref="r1",
            coordinate_space="geographic",
        )
        assert obs.geometry_crs == "EPSG:4326"


# ── Edge Cases ────────────────────────────────────────────────────────────

class TestDetectionCandidateEdgeCases:
    def test_minimal_candidate(self):
        dc = DetectionCandidate(
            candidate_id="minimal-1",
            observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.0,
            rule_version="v1",
        )
        assert dc.score == 0.0
        assert dc.geometry is None
        assert dc.semantic_label is None

    def test_full_candidate_roundtrip(self):
        dc = DetectionCandidate(
            candidate_id="full-1",
            observation_refs=["obs-1", "obs-2"],
            temporal_extent={"start": "2026-05-01", "end": "2026-06-30"},
            candidate_type="water_extent_change",
            semantic_label="both",
            area_m2=15000.0,
            geometry={"type": "MultiPolygon", "coordinates": [[[[0,0],[1,0],[1,1],[0,1],[0,0]]]]},
            score=0.65,
            quality_summary=CandidateQualitySummary(mean_score=0.65, n_observations=2),
            coordinate_space="geographic",
            evidence_refs=["mask.tif", "polygons.geojson"],
            rule_version="ml-b2-v1",
        )
        data = json.loads(dc.model_dump_json())
        dc2 = DetectionCandidate.model_validate(data)
        assert dc2.candidate_id == dc.candidate_id
        assert dc2.semantic_label == "both"
        assert dc2.area_m2 == 15000.0
        assert dc2.quality_summary.mean_score == 0.65
        assert len(dc2.evidence_refs) == 2


# ── EvidenceRef ───────────────────────────────────────────────────────────

class TestEvidenceRef:
    def test_evidence_ref_minimal(self):
        ref = EvidenceRef(
            evidence_id="ev-001",
            source_asset_ref="s2_t1.tif",
            evidence_type="change_mask",
        )
        assert ref.evidence_id == "ev-001"
        assert ref.evidence_type == "change_mask"

    def test_evidence_ref_full(self):
        ref = EvidenceRef(
            evidence_id="ev-002",
            source_asset_ref="s2_t1.tif",
            derived_asset_ref="change_mask.tif",
            evidence_type="change_mask",
            description="Water extent change mask between T1 and T2",
            provenance={"model": "RandomForest", "threshold": 0.5},
        )
        assert ref.derived_asset_ref == "change_mask.tif"
        assert ref.provenance is not None
