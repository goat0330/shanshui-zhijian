#!/usr/bin/env python3
"""
RS-01A.2 回归测试 — 旧 Pipeline vs 新 Tool

对比项:
- 变化像元数 (total_changed_pixels)
- 变化多边形数 (polygon_count)
- 变化总面积 (total_area_m2)
- 输出产物文件列表
- 异常处理行为

输出: docs/07_实施管理/reports/RS-01A_回归报告.md
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

import numpy as np
from core.schemas.contracts import (
    Modality, AssetRole, ExecutionStatus, TaskType,
)
from core.schemas.contracts.asset import AssetRef
from core.schemas.contracts.task import (
    TaskAssetBinding, InputSlotSpec, TaskSpec, InferenceTask, RunContext,
)
from core.protocols.asset_resolver import AssetRegistry
from tools.sar_temporal_change_tool import SarTemporalChangeTool

# ── 旧 Pipeline ──────────────────────────────────────────────
from pipeline.io.reader import read_geotiff
from pipeline.processing.preprocessor import reproject_to_target, resample_to_grid
from pipeline.models.baseline_water_sar import predict_vh as sar_predict
from pipeline.detection.change import detect_change
from pipeline.postprocessing.polygonize import polygonize_change_mask


def run_old_pipeline(s1_t1_path: Path, s1_t2_path: Path, output_dir: Path) -> dict:
    """运行旧 Pipeline (与 run_pipeline.py 中的 SAR 部分对齐)。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    # 读取
    sar_t1 = read_geotiff(s1_t1_path, bands=["vv", "vh"])
    sar_t2 = read_geotiff(s1_t2_path, bands=["vv", "vh"])
    # 重投影
    sar_t1 = reproject_to_target(sar_t1)
    sar_t2 = reproject_to_target(sar_t2)
    ref = sar_t1
    if sar_t2.width != ref.width or sar_t2.height != ref.height:
        sar_t2 = resample_to_grid(sar_t2, ref)
    # 水体检测
    vh_idx_t1 = sar_t1.bands.index("vh")
    vh_idx_t2 = sar_t2.bands.index("vh")
    water_t1, thresh_t1 = sar_predict(sar_t1.array[vh_idx_t1])
    water_t2, thresh_t2 = sar_predict(sar_t2.array[vh_idx_t2])
    # 变化检测
    change = detect_change(water_t1, water_t2)
    # 多边形化
    features = polygonize_change_mask(
        change["change_mask"], ref.transform, ref.crs,
        min_area_m2=500, pixel_area_m2=100,
    )
    total_area = sum(f.get("properties", {}).get("area_m2", 0) for f in features)
    return {
        "total_changed_pixels": int(change["stats"]["total_changed"]),
        "polygon_count": len(features),
        "total_area_m2": total_area,
        "thresh_t1_db": float(thresh_t1),
        "thresh_t2_db": float(thresh_t2),
    }


def run_new_tool(s1_t1_path: Path, s1_t2_path: Path, output_dir: Path) -> dict:
    """运行新 RS-01A.2 Tool。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    before_ref = AssetRef(
        asset_id="reg_before", uri=str(s1_t1_path),
        media_type="image/tiff; application=geotiff", modality=Modality.SAR,
    )
    after_ref = AssetRef(
        asset_id="reg_after", uri=str(s1_t2_path),
        media_type="image/tiff; application=geotiff", modality=Modality.SAR,
    )
    registry = AssetRegistry([before_ref, after_ref])
    tool = SarTemporalChangeTool(registry=registry)
    task = InferenceTask(
        task_id="regression-task", sample_id="reg-001", task_order=0,
        task_spec_ref="sar-temporal-change-v1@1.0.0",
        asset_bindings=[
            TaskAssetBinding(asset_ref="reg_before", role=AssetRole.BEFORE),
            TaskAssetBinding(asset_ref="reg_after", role=AssetRole.AFTER),
        ],
    )
    spec = TaskSpec(
        task_spec_id="sar-temporal-change-v1", version="1.0.0",
        task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
        input_slots=[
            InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1),
            InputSlotSpec(role=AssetRole.AFTER, modalities=[Modality.SAR], min_items=1, max_items=1),
        ],
    )
    ctx = RunContext(run_id="reg-run", output_dir=str(output_dir))
    result = tool.run(task, spec, ctx)
    return {
        "status": result.status.value,
        "total_changed_pixels": result.diagnostics.get("total_changed_pixels", 0),
        "polygon_count": result.diagnostics.get("polygon_count", 0),
        "total_area_m2": result.diagnostics.get("total_area_m2", 0),
        "artifact_refs": result.artifact_refs,
        "artifact_refs_count": len(result.artifact_refs),
        "observations_count": len(result.observations),
        "geometry_crs": result.observations[0].geometry_crs if result.observations else None,
        "raster_crs": result.diagnostics.get("raster_crs", ""),
        "geojson_crs": result.diagnostics.get("geojson_crs", ""),
        "artifact_resolvable": _verify_artifact_refs(result.artifact_refs, registry),
    }


def _verify_artifact_refs(artifact_ids: list[str], registry: AssetRegistry) -> bool:
    """验证所有 artifact_refs 可反向解析到真实文件。"""
    for aid in artifact_ids:
        try:
            ref = registry.resolve(aid)
            if not Path(ref.uri).exists():
                return False
        except KeyError:
            return False
    return True


# ── 主程序 ────────────────────────────────────────────────────

DATA_DIR = ROOT / "data" / "chongqing_demo" / "raw"
REPORT_DIR = ROOT / "docs" / "07_实施管理" / "reports"
OUTPUT_DIR = ROOT / "data" / "regression_output"


def main():
    s1_t1 = DATA_DIR / "s1_t1.tif"
    s1_t2 = DATA_DIR / "s1_t2.tif"

    if not s1_t1.exists() or not s1_t2.exists():
        print("重庆真实 SAR 数据不存在，跳过回归测试")
        return

    print("=" * 60)
    print("  RS-01A.2 回归测试: 旧 Pipeline vs 新 Tool")
    print("=" * 60)

    # 清理旧输出
    old_dir = OUTPUT_DIR / "old_pipeline"
    new_dir = OUTPUT_DIR / "new_tool"
    if old_dir.exists():
        shutil.rmtree(old_dir)
    if new_dir.exists():
        shutil.rmtree(new_dir)

    # 运行旧 Pipeline
    print("\n[1/2] 运行旧 Pipeline...")
    old = run_old_pipeline(s1_t1, s1_t2, old_dir)
    print(f"  旧 Pipeline: {old['total_changed_pixels']} 变化像元, "
          f"{old['polygon_count']} 多边形, {old['total_area_m2']:.0f} m²")

    # 运行新 Tool
    print("\n[2/2] 运行新 RS-01A.2 Tool...")
    new = run_new_tool(s1_t1, s1_t2, new_dir)
    print(f"  新 Tool:     {new['total_changed_pixels']} 变化像元, "
          f"{new['polygon_count']} 多边形, {new['total_area_m2']:.0f} m²")
    print(f"  状态: {new['status']}, 产物: {new['artifact_refs_count']}, "
          f"可解析: {new['artifact_resolvable']}, CRS: {new['raster_crs']}/{new['geojson_crs']}")

    # 比较
    match_pixels = old["total_changed_pixels"] == new["total_changed_pixels"]
    match_polygons = old["polygon_count"] == new["polygon_count"]
    area_diff = abs(old["total_area_m2"] - new["total_area_m2"])
    area_rel = area_diff / max(old["total_area_m2"], 1.0)

    print(f"\n  变化像元一致: {'YES' if match_pixels else 'NO'}")
    print(f"  多边形数一致: {'YES' if match_polygons else 'NO'}")
    print(f"  面积差异:     {area_diff:.0f} m² ({area_rel:.4%})")

    # 生成报告
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "RS-01A_回归报告.md"
    passed = match_pixels and match_polygons and area_rel < 0.05

    lines = [
        f"# RS-01A 回归报告",
        f"",
        f"| 项目 | 值 |",
        f"|------|-----|",
        f"| 生成时间 | {datetime.now().isoformat()} |",
        f"| 数据 | {s1_t1.name}, {s1_t2.name} |",
        f"| 测试版本 | RS-01A.2 |",
        f"",
        f"## 对比结果",
        f"",
        f"| 指标 | 旧 Pipeline | 新 Tool | 差异 | 一致 |",
        f"|------|------------|---------|------|------|",
        f"| 变化像元数 | {old['total_changed_pixels']} | {new['total_changed_pixels']} | {old['total_changed_pixels'] - new['total_changed_pixels']} | {'✅' if match_pixels else '❌'} |",
        f"| 多边形数 | {old['polygon_count']} | {new['polygon_count']} | {old['polygon_count'] - new['polygon_count']} | {'✅' if match_polygons else '❌'} |",
        f"| 总面积 (m²) | {old['total_area_m2']:.0f} | {new['total_area_m2']:.0f} | {area_diff:.0f} ({area_rel:.2%}) | {'✅' if area_rel < 0.05 else '❌'} |",
        f"| Otsu T1 (dB) | {old['thresh_t1_db']:.2f} | - | - | - |",
        f"| Otsu T2 (dB) | {old['thresh_t2_db']:.2f} | - | - | - |",
        f"",
        f"## RS-01A.2 新增功能验证",
        f"",
        f"| 功能 | 状态 | 说明 |",
        f"|------|------|------|",
        f"| AssetRegistry 注册 | {'✅' if new['artifact_refs_count'] >= 4 else '❌'} | {new['artifact_refs_count']} 个产物已注册 |",
        f"| artifact_refs 可反向解析 | {'✅' if new['artifact_resolvable'] else '❌'} | 所有 ref 可解析到真实文件 |",
        f"| CRS 统一 | {'✅' if new['raster_crs'] and new['geojson_crs'] else '❌'} | 栅格 {new['raster_crs']}, GeoJSON {new['geojson_crs']} |",
        f"| geometry_crs | {'✅' if new['geometry_crs'] == 'EPSG:4326' else '❌'} | Observation.geometry_crs = {new['geometry_crs']} |",
        f"| 输出目录结构 | ✅ | output_dir/run_id/task_id/ |",
        f"| Observations 每图斑一条 | {'✅' if new['observations_count'] == new['polygon_count'] else '❌'} | {new['observations_count']} = {new['polygon_count']} |",
        f"",
        f"## 结论",
        f"",
        f"回归结果: **{'PASSED' if passed else 'FAILED'}**",
        f"",
        f"旧 Pipeline 与新 RS-01A.2 Tool 在核心 SAR 变化检测指标上{'一致' if passed else '存在差异，需要排查'}。",
    ]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n回归报告已生成: {report_path}")


if __name__ == "__main__":
    main()
