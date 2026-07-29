"""
RS-01B-2 — 多时相回归验证脚本

验证:
1. 双时相 pair 回归与 RS-01A.2 一致 (10498 px / 510 polygons / 769500 m²)
2. 多时相模式可运行 (复用 pair 数据的 HISTORY + CURRENT 配置)
3. 产物完整性
"""

import json
import tempfile
import sys
from pathlib import Path
from datetime import datetime

# 固定 stdout 编码，避免 Windows 控制台输出中文和符号时乱码。
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

import rasterio
import numpy as np

from core.schemas.contracts import (
    ExecutionStatus, TaskType, AssetRole, Modality, SpatialReliability,
)
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.task import (
    InferenceTask, TaskSpec, RunContext, TaskAssetBinding, InputSlotSpec,
)
from core.protocols.asset_resolver import AssetRegistry
from core.schemas.contracts.run_manifest import RunManifestBuilder, RunStatus
from tools.sar_temporal_change_tool import SarTemporalChangeTool

# ── 真实数据路径 ──────────────────────────────────────────────

DATA_DIR = ROOT / "data" / "chongqing_demo" / "raw"
T1_PATH = DATA_DIR / "s1_t1.tif"
T2_PATH = DATA_DIR / "s1_t2.tif"
OUTPUT_DIR = ROOT / "output" / "regression_rs01b2"


def register_real_assets(registry: AssetRegistry) -> tuple[AssetRef, AssetRef]:
    """注册重庆真实 S1 数据。"""
    for label, path in [("s1_before", T1_PATH), ("s1_after", T2_PATH)]:
        with rasterio.open(path) as src:
            t = src.transform
            transform_list = [float(t.a), float(t.b), float(t.c),
                              float(t.d), float(t.e), float(t.f)]
            asset = AssetRef(
                asset_id=label,
                uri=str(path),
                media_type="image/tiff; application=geotiff",
                modality=Modality.SAR,
                spatial=SpatialMetadata(
                    reliability=SpatialReliability.GEOREFERENCED,
                    crs=str(src.crs).upper(),
                    transform=transform_list,
                    width=src.width,
                    height=src.height,
                ),
                bands=["vv", "vh"],
                acquisition_time=(
                    "2024-06-15T00:00:00Z" if "before" in label
                    else "2024-10-15T00:00:00Z"
                ),
            )
        registry.register(asset)

    return registry.resolve("s1_before"), registry.resolve("s1_after")


EXPECTED_PX = 10498
EXPECTED_POLY = 510
EXPECTED_AREA = 769500


def run_pair_regression():
    """双时相回归测试。"""
    print("=" * 60)
    print("RS-01B-2 双时相回归验证")
    print("=" * 60)

    registry = AssetRegistry()
    before_ref, after_ref = register_real_assets(registry)

    spec = TaskSpec(
        task_spec_id="sar-temporal-change-v1",
        version="1.0.0",
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
        task_id="reg-pair-rs01b2",
        sample_id="chongqing-pair",
        task_order=0,
        task_spec_ref="sar-temporal-change-v1@1.0.0",
        asset_bindings=[
            TaskAssetBinding(asset_ref="s1_before", role=AssetRole.BEFORE),
            TaskAssetBinding(asset_ref="s1_after", role=AssetRole.AFTER),
        ],
    )

    ctx = RunContext(
        run_id="reg-run-rs01b2",
        output_dir=str(OUTPUT_DIR),
    )

    tool = SarTemporalChangeTool(registry)
    result = tool.run(task, spec, ctx)

    diag = result.diagnostics
    total_px = diag.get("total_changed_pixels", 0)
    total_poly = diag.get("polygon_count", 0)
    total_area = diag.get("total_area_m2", 0)

    print(f"\n回归结果 vs RS-01A.2:")
    print(f"  total_changed_pixels:  {total_px}  (期望 {EXPECTED_PX})")
    print(f"  polygon_count:         {total_poly}  (期望 {EXPECTED_POLY})")
    print(f"  total_area_m2:         {total_area:.0f}  (期望 {EXPECTED_AREA})")

    ok = True
    if total_px != EXPECTED_PX:
        print(f"  ❌ 像元数不匹配")
        ok = False
    else:
        print(f"  ✅ 像元数一致")

    if total_poly != EXPECTED_POLY:
        print(f"  ❌ 图斑数不匹配")
        ok = False
    else:
        print(f"  ✅ 图斑数一致")

    if abs(total_area - EXPECTED_AREA) > 1.0:
        print(f"  ❌ 面积不匹配 (差 {total_area - EXPECTED_AREA:.1f} m²)")
        ok = False
    else:
        print(f"  ✅ 面积一致")

    # 验证产物
    task_output = OUTPUT_DIR / ctx.run_id / task.task_id
    products = list(task_output.glob("*.tif")) + list(task_output.glob("*.geojson"))
    print(f"\n产物: {len(products)} 个")
    for p in products:
        print(f"  ✓ {p.name}")

    return ok


def run_multi_temporal_real():
    """多时相真实数据验证 (用 T1 作为历史, T2 作为当前)。"""
    print("\n" + "=" * 60)
    print("RS-01B-2 多时相真实数据验证")
    print("=" * 60)

    registry = AssetRegistry()
    before_ref, after_ref = register_real_assets(registry)

    # 把 T1 复制为 6 景"历史", T2 作为"当前"
    # (简化: 用同一文件的不同 asset_id 模拟)
    import shutil
    mt_dir = Path(tempfile.mkdtemp(prefix="mt_real_"))

    history_refs = []
    for i in range(6):
        dest = mt_dir / f"s1_history_{i:03d}.tif"
        shutil.copy(T1_PATH, dest)
        ref = AssetRef(
            asset_id=f"mt_history_{i:03d}",
            uri=str(dest),
            media_type="image/tiff; application=geotiff",
            modality=Modality.SAR,
            spatial=before_ref.spatial,
            bands=["vv", "vh"],
            acquisition_time=f"2024-{6+i//2:02d}-{1+(i*5)%28:02d}T00:00:00Z",
        )
        registry.register(ref)
        history_refs.append(ref)

    dest = mt_dir / "s1_current_000.tif"
    shutil.copy(T2_PATH, dest)
    current_ref = AssetRef(
        asset_id="mt_current_000",
        uri=str(dest),
        media_type="image/tiff; application=geotiff",
        modality=Modality.SAR,
        spatial=after_ref.spatial,
        bands=["vv", "vh"],
        acquisition_time="2025-01-15T00:00:00Z",
    )
    registry.register(current_ref)

    spec = TaskSpec(
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

    bindings = []
    for i, r in enumerate(history_refs):
        bindings.append(TaskAssetBinding(
            asset_ref=r.asset_id, role=AssetRole.HISTORY, sequence_index=i,
        ))
    bindings.append(TaskAssetBinding(
        asset_ref="mt_current_000", role=AssetRole.CURRENT, sequence_index=0,
    ))

    task = InferenceTask(
        task_id="reg-mt-rs01b2",
        sample_id="chongqing-mt",
        task_order=0,
        task_spec_ref="sar-multi-temporal-v1@1.0.0",
        asset_bindings=bindings,
    )

    ctx = RunContext(
        run_id="reg-mt-run-rs01b2",
        output_dir=str(OUTPUT_DIR),
        tool_config={
            "multi_temporal": {
                "insufficient_history_policy": "fallback_to_pair",
                "min_history_scenes": 1,
                "valid_count_threshold": 3,
                "mad_epsilon": 0.001,
                "zscore_threshold": 3.0,
                "water_occurrence_threshold": 0.3,
                "min_area_m2": 500,
                "pixel_area_m2": 100,
            },
        },
    )

    tool = SarTemporalChangeTool(registry)
    result = tool.run(task, spec, ctx)

    print(f"\n状态: {result.status.value}")
    print(f"模式: {result.diagnostics.get('mode', 'unknown')}")
    print(f"历史景数: {result.diagnostics.get('n_history', '?')}")
    print(f"当前景数: {result.diagnostics.get('n_current', '?')}")
    print(f"当前模式: {result.diagnostics.get('current_mode', '?')}")

    stats = result.diagnostics.get("change_stats", {})
    print(f"变化像元: {stats.get('total_changed_pixels', '?')}")
    print(f"图斑数: {result.diagnostics.get('polygon_count', '?')}")
    print(f"面积: {result.diagnostics.get('total_area_m2', 0):.0f} m²")

    # 验证产物
    task_output = OUTPUT_DIR / ctx.run_id / task.task_id
    expected_files = [
        "baseline_vh_median.tif", "baseline_vh_mad.tif",
        "history_valid_count.tif", "historical_water_occurrence.tif",
        "current_vh_median.tif", "current_water_mask.tif",
        "robust_zscore.tif", "water_gain_mask.tif",
        "water_loss_mask.tif", "final_change_mask.tif",
        "candidates.geojson", "run_report.json",
    ]
    missing = [f for f in expected_files if not (task_output / f).exists()]
    if missing:
        print(f"❌ 缺失产物: {missing}")
        return False
    print("✅ 所有产物完整")

    shutil.rmtree(mt_dir, ignore_errors=True)
    return result.status in (ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
                              ExecutionStatus.SUCCEEDED_EMPTY)


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 创建 RunManifest ─────────────────────────────────────
    manifest = RunManifestBuilder.create(
        run_id="reg-rs01b2",
        task_id="reg-pair-rs01b2,reg-mt-rs01b2",
        task_spec_ref="sar-temporal-change-v1@1.0.0;sar-multi-temporal-v1@1.0.0",
        run_command="python scripts/run_regression_rs01b2.py",
    )
    manifest = RunManifestBuilder.add_input_asset(
        manifest, asset_id="s1_before", uri=str(T1_PATH))
    manifest = RunManifestBuilder.add_input_asset(
        manifest, asset_id="s1_after", uri=str(T2_PATH))

    pair_ok = run_pair_regression()
    mt_ok = run_multi_temporal_real()
    all_ok = pair_ok and mt_ok

    # ── 完成 Manifest ────────────────────────────────────────
    if all_ok:
        manifest = RunManifestBuilder.succeed(manifest)
    else:
        manifest = RunManifestBuilder.fail(
            manifest, "regression",
            "pair_failed" if not pair_ok else "multi_temporal_failed",
            "Regression checks failed")
    manifest_path = OUTPUT_DIR / "run_manifest.json"
    manifest.save(manifest_path)
    print(f"\nRunManifest: {manifest_path}")
    print(f"  SHA256: {manifest.manifest_sha256}")

    print("\n" + "=" * 60)
    print(f"pair 回归: {'✅ PASS' if pair_ok else '❌ FAIL'}")
    print(f"多时相:    {'✅ PASS' if mt_ok else '❌ FAIL'}")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)
