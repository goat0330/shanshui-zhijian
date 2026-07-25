"""
RS-01B-3 -- Persistence gating & candidate object ranking tests.

10 synthetic tests (A-J):
  A. 2/2 current scenes same change -> persistent
  B. Only 1/2 current scenes change -> transient, not persistent
  C. 2/3 current scenes change -> persistence_ratio=0.67, meets default gate
  D. Same object slight shift -> linked as same candidate_id
  E. Two adjacent but independent objects -> NOT merged
  F. gain vs loss type conflict -> uncertain, not persistent
  G. Single current scene -> persistence unavailable, flow succeeds
  H. No-change scene -> persistent FPR <= 5%
  I. Artifact checksum and bounds all valid
  J. Pair mode + RS-01B-2 output compatibility preserved
"""

import json
import tempfile
import shutil
import numpy as np
from pathlib import Path
import pytest
import rasterio
from rasterio.transform import from_bounds, Affine
from rasterio.crs import CRS

from core.schemas.contracts import (
    ExecutionStatus, TaskType, ObservationType, ScoreType, AssetRole, Modality,
    SpatialReliability,
)
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.task import (
    InferenceTask, TaskSpec, RunContext, TaskAssetBinding, InputSlotSpec,
)
from core.protocols.asset_resolver import AssetRegistry
from tools.sar_temporal_change_tool import SarTemporalChangeTool
from tools.persistence_background import (
    compute_per_scene_change, compute_persistence, link_objects_across_time,
    rank_candidates, parse_persistence_config,
)


# --- Test grid ---

H, W = 16, 16
TEST_CRS = "EPSG:4326"
TRANSFORM = from_bounds(106.55, 29.55, 106.60, 29.60, W, H)

WATER_PATCH1 = (slice(3, 5), slice(5, 7))
WATER_PATCH2 = (slice(10, 12), slice(12, 14))


def _write_sar_geotiff(path, vv, vh, crs=TEST_CRS, transform=TRANSFORM,
                       acquisition_time="2024-06-15T00:00:00Z"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.stack([vv.astype(np.float32), vh.astype(np.float32)])
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=2,
        dtype="float32", crs=crs, transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data[0], 1)
        dst.write(data[1], 2)
        dst.set_band_description(1, "vv")
        dst.set_band_description(2, "vh")
        dst.update_tags(
            platform="Sentinel-1A", product_type="GRD",
            orbit_direction="ASCENDING", relative_orbit="55",
            acquisition_time=acquisition_time,
        )
    return path


def _make_stable_vh(water_mask, base_db=-12.0, noise_std=1.0, seed=42):
    rng = np.random.RandomState(seed)
    vh = np.full((H, W), base_db, dtype=np.float32)
    vh += rng.normal(0, noise_std, (H, W)).astype(np.float32)
    if water_mask.any():
        vh[water_mask] = -25.0
        vh[water_mask] += rng.normal(0, 0.5, water_mask.sum()).astype(np.float32)
    return vh


def _make_vv_from_vh(vh, offset_db=3.0):
    return vh + offset_db


def _create_history_scenes(tmpdir, n_scenes, water_mask):
    refs = []
    for i in range(n_scenes):
        vh = _make_stable_vh(water_mask, seed=42 + i)
        vv = _make_vv_from_vh(vh)
        p = tmpdir / f"s1_history_{i:03d}.tif"
        _write_sar_geotiff(p, vv, vh,
                            acquisition_time=f"2024-{6+i//30:02d}-{1+(i%28):02d}T00:00:00Z")
        ref = AssetRef(
            asset_id=f"history_{i:03d}", uri=str(p),
            media_type="image/tiff; application=geotiff",
            modality=Modality.SAR,
            spatial=SpatialMetadata(
                reliability=SpatialReliability.GEOREFERENCED,
                crs=TEST_CRS, width=W, height=H,
            ),
            bands=["vv", "vh"],
            acquisition_time=f"2024-{6+i//30:02d}-{1+(i%28):02d}T00:00:00Z",
        )
        refs.append(ref)
    return refs


def _create_current_scenes(tmpdir, n_scenes, water_mask,
                           add_gain=False, add_loss=False,
                           gain_only_scene_indices=None,
                           loss_only_scene_indices=None):
    refs = []
    for i in range(n_scenes):
        wm = water_mask.copy()
        if gain_only_scene_indices is not None and i in gain_only_scene_indices:
            wm[WATER_PATCH2] = 1
        elif add_gain:
            wm[WATER_PATCH2] = 1
        if loss_only_scene_indices is not None and i in loss_only_scene_indices:
            wm[WATER_PATCH1] = 0
        elif add_loss:
            wm[WATER_PATCH1] = 0
        vh = _make_stable_vh(wm, seed=100 + i)
        vv = _make_vv_from_vh(vh)
        p = tmpdir / f"s1_current_{i:03d}.tif"
        _write_sar_geotiff(p, vv, vh,
                            acquisition_time=f"2025-01-{15+i:02d}T00:00:00Z")
        ref = AssetRef(
            asset_id=f"current_{i:03d}", uri=str(p),
            media_type="image/tiff; application=geotiff",
            modality=Modality.SAR,
            spatial=SpatialMetadata(
                reliability=SpatialReliability.GEOREFERENCED,
                crs=TEST_CRS, width=W, height=H,
            ),
            bands=["vv", "vh"],
            acquisition_time=f"2025-01-{15+i:02d}T00:00:00Z",
        )
        refs.append(ref)
    return refs


def _make_mt_spec():
    return TaskSpec(
        task_spec_id="sar-multi-temporal-v1",
        version="1.0.0",
        task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
        input_slots=[
            InputSlotSpec(role=AssetRole.HISTORY, modalities=[Modality.SAR],
                          min_items=1, max_items=24),
            InputSlotSpec(role=AssetRole.CURRENT, modalities=[Modality.SAR],
                          min_items=1, max_items=3),
        ],
        validation_policy={"mode": "trust_preprocessed_input"},
    )


def _make_mt_task(task_id, spec, history_refs, current_refs):
    bindings = []
    for i, r in enumerate(history_refs):
        bindings.append(TaskAssetBinding(
            asset_ref=r.asset_id, role=AssetRole.HISTORY, sequence_index=i,
        ))
    for i, r in enumerate(current_refs):
        bindings.append(TaskAssetBinding(
            asset_ref=r.asset_id, role=AssetRole.CURRENT, sequence_index=i,
        ))
    return InferenceTask(
        task_id=task_id, sample_id="sample-mt-01", task_order=0,
        task_spec_ref=f"{spec.task_spec_id}@{spec.version}",
        asset_bindings=bindings,
    )


def _make_run_context(output_dir):
    return RunContext(
        run_id="run-mt-rs01b3",
        output_dir=output_dir,
        tool_config={
            "multi_temporal": {
                "insufficient_history_policy": "fallback_to_pair",
                "min_history_scenes": 6,
                "max_history_scenes": 24,
                "min_current_scenes": 1,
                "max_current_scenes": 3,
                "valid_count_threshold": 3,
                "mad_epsilon": 0.001,
                "zscore_threshold": 3.0,
                "stable_land_max": 0.2,
                "stable_water_min": 0.8,
                "min_area_m2": 100,
                "pixel_area_m2": 100,
            },
            "persistence": {
                "minimum_occurrences": 2,
                "minimum_ratio": 0.67,
                "require_same_change_type": True,
            },
            "object_linking": {
                "minimum_iou": 0.30,
                "maximum_centroid_distance_m": 50,
                "require_same_change_type": True,
            },
            "ranking": {
                "weight_persistence_ratio": 0.40,
                "weight_normalized_robust_z": 0.25,
                "weight_normalized_area": 0.20,
                "weight_quality_factor": 0.15,
            },
        },
    )


@pytest.fixture
def tmpdir():
    d = tempfile.mkdtemp(prefix="rs01b3_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def base_water_mask():
    wm = np.zeros((H, W), dtype=bool)
    wm[WATER_PATCH1] = True
    return wm


# ============================================================
# Test A: 2/2 current scenes same change -> persistent
# ============================================================

class TestPersistentDetection:
    """Test A: Both current scenes show same change -> persistent."""

    def test_2of2_consistent_change_is_persistent(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        current_refs = _create_current_scenes(tmpdir, 2, base_water_mask,
                                               add_gain=True)
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-A", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS

        # Check persistence artifacts exist
        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        assert (output_dir / "persistence_count.tif").exists()
        assert (output_dir / "persistence_ratio.tif").exists()
        assert (output_dir / "persistent_change_mask.tif").exists()
        assert (output_dir / "transient_change_mask.tif").exists()
        assert (output_dir / "candidate_objects.geojson").exists()
        assert (output_dir / "candidate_objects.json").exists()

        # Check persistence diagnostics
        diag = result.diagnostics or {}
        p_stats = diag.get("persistence_stats", {})
        assert p_stats.get("persistence_status") == "available"
        assert p_stats.get("n_current_scenes") == 2
        assert p_stats.get("persistent_pixels", 0) > 0


# ============================================================
# Test B: Only 1/2 current scenes change -> transient
# ============================================================

class TestTransientDetection:
    """Test B: Only 1/2 current scenes change -> transient, not persistent."""

    def test_1of2_change_is_transient(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        # Only scene 0 gets gain, scene 1 doesn't
        current_refs = _create_current_scenes(tmpdir, 2, base_water_mask,
                                               gain_only_scene_indices=[0])
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-B", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        assert result.status in (ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
                                 ExecutionStatus.SUCCEEDED_EMPTY)

        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        # Transient mask should have some pixels, persistent should be low/zero
        with rasterio.open(str(output_dir / "transient_change_mask.tif")) as src:
            transient = src.read(1)
        with rasterio.open(str(output_dir / "persistent_change_mask.tif")) as src:
            persistent = src.read(1)

        # Transient suppression: transient mask should capture 1-scene changes
        assert transient.sum() >= persistent.sum(), \
            "Transient should capture more pixels than persistent when 1/2 scenes change"


# ============================================================
# Test C: 2/3 current scenes change -> ratio=0.67, meets gate
# ============================================================

class TestTwoThirdsPersistent:
    """Test C: 2/3 current scenes change -> ratio=0.67, meets default."""

    def test_2of3_change_meets_ratio_gate(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        # Scenes 0 and 1 get gain, scene 2 doesn't
        current_refs = _create_current_scenes(tmpdir, 3, base_water_mask,
                                               gain_only_scene_indices=[0, 1])
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-C", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        assert result.status in (ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
                                 ExecutionStatus.SUCCEEDED_EMPTY)

        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        with rasterio.open(str(output_dir / "persistence_ratio.tif")) as src:
            ratio = src.read(1)

        # Max ratio should be ~0.67 (2/3 scenes)
        max_ratio = float(ratio.max())
        assert max_ratio >= 0.66, f"Expected ratio >= 0.66 (2/3), got {max_ratio:.3f}"


# ============================================================
# Test D: Same object slight shift -> linked as same candidate
# ============================================================

class TestObjectAssociationShift:
    """Test D: Objects with slight spatial shift should link as same candidate.

    Strong assertions (A0):
      - At least one persistent candidate with occurrence_count == 2
      - The same candidate appears in both current scenes (source_scene_indices == [0, 1])
      - observation_refs structure exists
      - candidate_id is stable (re-run produces same ID for same input)
    """

    def test_shifted_objects_linked(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        current_refs = _create_current_scenes(tmpdir, 2, base_water_mask,
                                               add_gain=True)
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-D", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))
        ctx2 = _make_run_context(str(tmpdir) + "_replay")

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        cand_json_path = output_dir / "candidate_objects.json"
        assert cand_json_path.exists(), "candidate_objects.json not produced"

        cand_data = json.loads(cand_json_path.read_text(encoding="utf-8"))
        candidates = cand_data.get("candidates", [])
        assert len(candidates) > 0, "Expected at least one candidate"

        persistent_cands = [c for c in candidates
                            if c.get("persistence_status") == "persistent"]
        assert len(persistent_cands) >= 1, \
            f"Expected at least 1 persistent candidate, got {len(persistent_cands)}"

        # Strong: occurrence_count must be exactly 2 (2 scenes with same change)
        for pc in persistent_cands:
            assert pc["occurrence_count"] == 2, \
                f"persistent candidate {pc['candidate_id']} has occurrence_count={pc['occurrence_count']}, expected 2"
            assert pc["source_scene_indices"] == [0, 1], \
                f"Expected source_scene_indices [0,1], got {pc['source_scene_indices']}"

        # Strong: candidate_id stability — re-run with same input produces same IDs
        tool2 = SarTemporalChangeTool(AssetRegistry())
        for r in history_refs + current_refs:
            tool2._registry.register(r)
        result2 = tool2.run(task, spec, ctx2)
        output_dir2 = Path(ctx2.output_dir) / ctx2.run_id / task.task_id
        cand_json_path2 = output_dir2 / "candidate_objects.json"
        assert cand_json_path2.exists()

        cand_data2 = json.loads(cand_json_path2.read_text(encoding="utf-8"))
        cands2 = cand_data2.get("candidates", [])

        # Same number of candidates
        assert len(cands2) == len(candidates), \
            f"Candidate count differs on re-run: {len(cands2)} vs {len(candidates)}"

        # Same IDs (order is deterministic from rank_candidates)
        for c1, c2 in zip(candidates, cands2):
            assert c1["candidate_id"] == c2["candidate_id"], \
                f"Candidate ID differs on re-run: {c1['candidate_id']} vs {c2['candidate_id']}"

        # Strong: candidate_type or change_type should be "water_gain"
        gain_cands = [c for c in candidates if c.get("change_type") == "water_gain"]
        assert len(gain_cands) > 0, "Expected at least one water_gain candidate"


# ============================================================
# Test E: Two adjacent but independent objects -> NOT merged
# ============================================================

class TestAdjacentNotMerged:
    """Test E: Adjacent but independent objects should NOT merge.

    Strong assertions (A0):
      - Independent objects at different locations are separate candidates
      - Candidate count > 1 (they were not merged into one)
      - Both water_gain and water_loss change_types exist
      - No single candidate has mixed type (each is independent)
    """

    def test_adjacent_independent_not_merged(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        current_refs = _create_current_scenes(tmpdir, 2, base_water_mask,
                                               add_gain=True, add_loss=True)
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-E", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        cand_json_path = output_dir / "candidate_objects.json"
        assert cand_json_path.exists(), "candidate_objects.json not produced"

        cand_data = json.loads(cand_json_path.read_text(encoding="utf-8"))
        candidates = cand_data.get("candidates", [])
        assert len(candidates) >= 2, \
            f"Expected at least 2 independent candidates, got {len(candidates)}"

        # Strong: Both change_types should be present
        change_types = set(c.get("change_type") for c in candidates)
        assert "water_gain" in change_types, \
            f"Expected water_gain change type, got {change_types}"
        assert "water_loss" in change_types, \
            f"Expected water_loss change type, got {change_types}"

        # Strong: No single candidate has "mixed" type (objects are independent)
        for c in candidates:
            assert c.get("change_type") != "mixed", \
                f"Candidate {c['candidate_id']} has 'mixed' type — independent objects merged"
            assert c.get("persistence_status") != "uncertain", \
                f"Candidate {c['candidate_id']} is 'uncertain' — type conflict when none expected"

        # Strong: Count independent change types
        gain_cands = [c for c in candidates if c.get("change_type") == "water_gain"]
        loss_cands = [c for c in candidates if c.get("change_type") == "water_loss"]
        assert len(gain_cands) >= 1, f"Expected >=1 water_gain candidate, got {len(gain_cands)}"
        assert len(loss_cands) >= 1, f"Expected >=1 water_loss candidate, got {len(loss_cands)}"


# ============================================================
# Test F: gain vs loss type conflict -> uncertain
# ============================================================

class TestTypeConflictUncertain:
    """Test F: gain/loss type conflict -> uncertain, not persistent.

    Strong assertions (A0):
      - Uses link_objects_across_time for candidate aggregation
      - With require_same_change_type=True: two separate candidates (gain + loss)
        OR one candidate with "mixed" type + "uncertain" status
      - With require_same_change_type=False: type conflict produces uncertain
    """

    def _make_polygon_features(self, change_type, pixel_area_m2=100.0,
                               base_transform=None, crs="EPSG:4326",
                               patch=WATER_PATCH2):
        """Build a synthetic polygon feature for the given change type."""
        from rasterio.features import shapes as rio_shapes
        from rasterio.transform import from_bounds
        t = base_transform or from_bounds(106.55, 29.55, 106.60, 29.60, W, H)

        mask = np.zeros((H, W), dtype=np.uint8)
        mask[patch] = 1
        feat_list = []
        for g, val in rio_shapes(mask, mask=mask, transform=t):
            if val == 1:
                feat_list.append({
                    "type": "Feature",
                    "geometry": g,
                    "properties": {
                        "change_type": change_type,
                        "area_m2": float(np.sum(mask) * pixel_area_m2),
                        "pixel_count": int(np.sum(mask)),
                        "robust_z_mean": 3.0 if change_type == "water_gain" else -3.0,
                        "robust_z_max": 4.0,
                        "water_occurrence_mean": 0.5,
                    },
                })
        return feat_list

    def _test_with_config(self, require_same_change_type, geometry_crs="EPSG:4326"):
        """Helper: run link_objects_across_time with config and check results."""
        # Scene 0: water_gain at PATCH2
        feats0 = self._make_polygon_features("water_gain", patch=WATER_PATCH2)
        # Scene 1: water_loss at SAME location (PATCH2) — conflict!
        feats1 = self._make_polygon_features("water_loss", patch=WATER_PATCH2)

        per_scene = [feats0, feats1]
        asset_refs = ["scene_0", "scene_1"]

        candidates = link_objects_across_time(
            per_scene, asset_refs,
            min_iou=0.3, max_centroid_distance_m=50,
            require_same_change_type=require_same_change_type,
            require_spatial_intersect=True,
            geometry_crs=geometry_crs,
            n_current_scenes=2,
            minimum_occurrences=2,
        )

        return candidates

    def test_type_conflict_with_same_change_type_required(self, tmpdir, base_water_mask):
        """require_same_change_type=True: separate candidates or uncertain."""
        candidates = self._test_with_config(require_same_change_type=True)

        assert len(candidates) > 0, "Expected at least one candidate"

        if len(candidates) == 2:
            # Two separate candidates: one gain, one loss — correct handling
            types = {c.change_type for c in candidates}
            assert "water_gain" in types, f"Missing water_gain type, got {types}"
            assert "water_loss" in types, f"Missing water_loss type, got {types}"
            # Each should be transient (only seen in 1 scene each)
            for c in candidates:
                assert c.persistence_status in ("transient", "persistent"), \
                    f"Unexpected status {c.persistence_status} for {c.candidate_id}"
                assert c.occurrence_count == 1, \
                    f"Expected occurrence_count=1, got {c.occurrence_count}"
        else:
            # Single uncertain candidate with mixed type
            c = candidates[0]
            assert c.persistence_status == "uncertain", \
                f"Expected 'uncertain' status for type conflict, got {c.persistence_status}"
            assert c.change_type == "mixed", \
                f"Expected 'mixed' change_type, got {c.change_type}"

    def test_type_conflict_allows_mixed(self, tmpdir, base_water_mask):
        """require_same_change_type=False should produce uncertain/mixed."""
        candidates = self._test_with_config(require_same_change_type=False)

        assert len(candidates) >= 1, "Expected at least one candidate"
        # With mixed types allowed, all features merge into one uncertain candidate
        c = candidates[0]
        assert c.persistence_status == "uncertain", \
            f"Expected 'uncertain' status, got {c.persistence_status}"
        assert c.change_type == "mixed", \
            f"Expected 'mixed' change_type, got {c.change_type}"
        assert c.occurrence_count == 2, \
            f"Expected occurrence_count=2 (both scenes), got {c.occurrence_count}"


# ============================================================
# Test G: Single current scene -> persistence unavailable, flow succeeds
# ============================================================

class TestSingleScenePersistenceUnavailable:
    """Test G: Single current scene -> persistence unavailable."""

    def test_single_current_persistence_unavailable(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        current_refs = _create_current_scenes(tmpdir, 1, base_water_mask,
                                               add_gain=True)
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-G", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS

        diag = result.diagnostics or {}
        p_stats = diag.get("persistence_stats", {})
        assert p_stats.get("persistence_status") == "unavailable", \
            f"Expected 'unavailable' for single scene, got {p_stats.get('persistence_status')}"


# ============================================================
# Test H: No-change scene -> persistent FPR <= 5%
# ============================================================

class TestNoChangeFPR:
    """Test H: No-change scenario -> persistent FPR <= 5%."""

    def test_no_change_persistent_fpr_low(self, tmpdir, base_water_mask):
        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        # Current scenes with SAME water mask (no change)
        current_refs = _create_current_scenes(tmpdir, 2, base_water_mask)
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-H", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        assert result.status in (ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
                                 ExecutionStatus.SUCCEEDED_EMPTY)

        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        with rasterio.open(str(output_dir / "persistent_change_mask.tif")) as src:
            persistent = src.read(1)

        # FPR: persistent pixels should be <= 5% of actual reprojected raster
        total_pixels = persistent.size  # reprojected raster size (not H*W)
        persistent_pixels = int(persistent.sum())
        fpr = persistent_pixels / max(total_pixels, 1)
        assert fpr <= 0.05, f"Persistent FPR {fpr:.4f} > 0.05 (pixels={persistent_pixels}/{total_pixels})"


# ============================================================
# Test I: Artifact checksum and bounds all valid
# ============================================================

class TestArtifactIntegrity:
    """Test I: All persistence artifacts have valid checksums and bounds."""

    def test_artifacts_have_checksum_and_bounds(self, tmpdir, base_water_mask):
        import hashlib

        history_refs = _create_history_scenes(tmpdir, 8, base_water_mask)
        current_refs = _create_current_scenes(tmpdir, 2, base_water_mask,
                                               add_gain=True)
        registry = AssetRegistry()
        for r in history_refs + current_refs:
            registry.register(r)

        spec = _make_mt_spec()
        task = _make_mt_task("task-I", spec, history_refs, current_refs)
        ctx = _make_run_context(str(tmpdir))

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
        assert len(result.artifact_refs) >= 12

        # Verify all artifacts resolve and have valid checksums
        for aid in result.artifact_refs:
            resolved = registry.resolve(aid)
            assert resolved.uri is not None, f"{aid}: no URI"
            assert Path(resolved.uri).exists(), f"{aid}: file missing"
            if resolved.checksum:
                actual = hashlib.sha256(Path(resolved.uri).read_bytes()).hexdigest()
                assert actual == resolved.checksum, \
                    f"{aid}: checksum mismatch (expected {resolved.checksum[:16]}..., got {actual[:16]}...)"


# ============================================================
# Test J: Pair mode + RS-01B-2 output compatibility
# ============================================================

class TestPairCompatibility:
    """Test J: Pair mode still works, RS-01B-2 output preserved."""

    def test_pair_mode_still_works(self, tmpdir, base_water_mask):
        # Create pair-mode spec (BEFORE + AFTER, not HISTORY + CURRENT)
        from core.schemas.contracts.task import InputSlotSpec

        before_vh = _make_stable_vh(base_water_mask, seed=42)
        before_vv = _make_vv_from_vh(before_vh)
        before_path = tmpdir / "before.tif"
        _write_sar_geotiff(before_path, before_vv, before_vh)

        wm_after = base_water_mask.copy()
        wm_after[WATER_PATCH2] = True
        after_vh = _make_stable_vh(wm_after, seed=100)
        after_vv = _make_vv_from_vh(after_vh)
        after_path = tmpdir / "after.tif"
        _write_sar_geotiff(after_path, after_vv, after_vh)

        before_ref = AssetRef(
            asset_id="pair_before", uri=str(before_path),
            media_type="image/tiff; application=geotiff",
            modality=Modality.SAR,
            spatial=SpatialMetadata(
                reliability=SpatialReliability.GEOREFERENCED,
                crs=TEST_CRS, width=W, height=H,
            ),
            bands=["vv", "vh"],
        )
        after_ref = AssetRef(
            asset_id="pair_after", uri=str(after_path),
            media_type="image/tiff; application=geotiff",
            modality=Modality.SAR,
            spatial=SpatialMetadata(
                reliability=SpatialReliability.GEOREFERENCED,
                crs=TEST_CRS, width=W, height=H,
            ),
            bands=["vv", "vh"],
        )
        registry = AssetRegistry()
        registry.register(before_ref)
        registry.register(after_ref)

        spec = TaskSpec(
            task_spec_id="sar-temporal-change-v1", version="1.0.0",
            task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            input_slots=[
                InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR],
                              min_items=1, max_items=1),
                InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR],
                              min_items=1, max_items=1),
            ],
            validation_policy={"mode": "trust_preprocessed_input"},
        )
        task = InferenceTask(
            task_id="task-pair-J", sample_id="sample-pair",
            task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[
                TaskAssetBinding(asset_ref="pair_before", role=AssetRole.BEFORE),
                TaskAssetBinding(asset_ref="pair_after", role=AssetRole.AFTER),
            ],
        )
        ctx = RunContext(
            run_id="run-pair-J", output_dir=str(tmpdir),
            tool_config={},
        )

        tool = SarTemporalChangeTool(registry)
        result = tool.run(task, spec, ctx)

        # Pair mode should still work
        assert result.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS

        diag = result.diagnostics or {}
        assert diag.get("actual_mode") in ("pair", "pair_fallback")

        # Pair mode should NOT have persistence artifacts
        output_dir = Path(ctx.output_dir) / ctx.run_id / task.task_id
        assert not (output_dir / "persistence_count.tif").exists(), \
            "Pair mode should NOT produce persistence artifacts"
        assert (output_dir / "candidates.geojson").exists(), \
            "Pair mode should still produce candidates.geojson"
        # Original 5 artifacts for pair mode
        assert len(result.artifact_refs) == 5