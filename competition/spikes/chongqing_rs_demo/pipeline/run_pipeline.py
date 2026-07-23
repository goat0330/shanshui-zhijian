#!/usr/bin/env python3
"""
山水智鉴 V0 Pipeline — 一键运行全链

用法:
    python pipeline/run_pipeline.py

流程:
    InputAdapter → Preprocessor(重投影) → FeatureExtractor → ModelClient
    → ChangeDetector → Polygonizer → ProductWriter
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for pipeline module

import json
from datetime import datetime
import numpy as np
from pipeline.io.reader import read_geotiff, validate_alignment
from pipeline.processing.preprocessor import reproject_to_target, resample_to_grid, check_and_report
from pipeline.features.spectral import compute_all_indices
from pipeline.features.sar import compute_sar_stats
from pipeline.models.baseline_water import predict as optical_predict
from pipeline.models.baseline_water_sar import predict_vh as sar_predict
from pipeline.fusion.water_extent import fuse_water_extent
from pipeline.detection.change import detect_change
from pipeline.postprocessing.polygonize import polygonize_change_mask, assign_change_type
from pipeline.io.writer import write_geotiff, write_geojson, write_jsonl, write_preview

# ── 路径配置 ──────────────────────────────────────────────────────
RAW_DIR = ROOT / "data" / "chongqing_demo" / "raw"
PRODUCTS_DIR = Path(__file__).resolve().parent.parent / "products"
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 60)
    print("  山水智鉴 V0 Pipeline")
    print("=" * 60)

    # ── Step 1: InputAdapter ────────────────────────────────────
    print("\n[1/6] InputAdapter — 读取数据")
    s2_t1 = read_geotiff(RAW_DIR / "s2_t1.tif",
                         bands=["blue", "green", "red", "nir", "swir1", "swir2"])
    s2_t2 = read_geotiff(RAW_DIR / "s2_t2.tif",
                         bands=["blue", "green", "red", "nir", "swir1", "swir2"])
    s1_t1 = read_geotiff(RAW_DIR / "s1_t1.tif", bands=["vv", "vh"])
    s1_t2 = read_geotiff(RAW_DIR / "s1_t2.tif", bands=["vv", "vh"])
    dem = read_geotiff(RAW_DIR / "dem_glo30.tif", bands=["elevation"])
    jrc = read_geotiff(RAW_DIR / "jrc_water_occurrence.tif", bands=["occurrence"])
    wc = read_geotiff(RAW_DIR / "worldcover_2021.tif", bands=["landcover"])

    # 检查各数据有效覆盖
    for name, ri in [("S2_T1", s2_t1), ("S2_T2", s2_t2)]:
        valid = np.isfinite(ri.array).sum()
        total = ri.array.size
        print(f"  {name}: 有效像元 {valid}/{total} ({valid/total*100:.1f}%)")

    # ── Step 2: Preprocessor — 重投影到 EPSG:4526 ─────────────
    print("\n[2/6] Preprocessor — 重投影到 EPSG:4526 (10m)")
    s2_t1 = reproject_to_target(s2_t1)
    s2_t2 = reproject_to_target(s2_t2)
    jrc = reproject_to_target(jrc)
    wc = reproject_to_target(wc)

    check_and_report([s2_t1, s2_t2, jrc, wc],
                     labels=["S2_T1_proj", "S2_T2_proj", "JRC_proj", "WC_proj"])

    # 统一 JRC/WC 到 S2 网格 (rasterio.warp.reproject, 保证地理参考一致性)
    ref = s2_t1  # S2 T1 为参考网格
    if jrc.width != ref.width or jrc.height != ref.height:
        print(f"  [Align] JRC ({jrc.width}x{jrc.height}) → S2 网格 ({ref.width}x{ref.height})")
        jrc = resample_to_grid(jrc, ref)
    if wc.width != ref.width or wc.height != ref.height:
        print(f"  [Align] WC ({wc.width}x{wc.height}) → S2 网格 ({ref.width}x{ref.height})")
        wc = resample_to_grid(wc, ref)

    # ── Step 3: FeatureExtractor ────────────────────────────────
    print("\n[3/6] FeatureExtractor — 光谱指数计算")
    indices_t1 = compute_all_indices(s2_t1)
    indices_t2 = compute_all_indices(s2_t2)

    for label, idx in [("T1", indices_t1), ("T2", indices_t2)]:
        ndwi = idx["ndwi"]
        valid = np.isfinite(ndwi)
        if valid.any():
            print(f"  NDWI_{label}: 均值={ndwi[valid].mean():.4f}, "
                  f"范围=[{ndwi[valid].min():.4f}, {ndwi[valid].max():.4f}], "
                  f"有效={valid.sum()}/{valid.size}")
        else:
            print(f"  ⚠️ NDWI_{label}: 全部为无效值 (云覆盖)")

    # ── Step 4: ModelClient V0 ─────────────────────────────────
    print("\n[4/7] ModelClient — 光学水体提取")
    jrc_arr = np.nan_to_num(jrc.array[0], nan=0)
    wc_arr = np.nan_to_num(wc.array[0], nan=0)

    # 检查原始波段数据有效性，而非 NDWI（NDWI 全 0 也会通过 finite 检查）
    green_band_t1 = s2_t1.array[s2_t1.bands.index("green")]
    green_band_t2 = s2_t2.array[s2_t2.bands.index("green")]
    t1_raw_valid = (np.isfinite(green_band_t1) & (green_band_t1 != 0)).sum() / green_band_t1.size
    t2_raw_valid = (np.isfinite(green_band_t2) & (green_band_t2 != 0)).sum() / green_band_t2.size
    common_valid_ratio = min(t1_raw_valid, t2_raw_valid)
    print(f"  T1 原始波段有效: {t1_raw_valid:.1%}, T2 原始波段有效: {t2_raw_valid:.1%}")

    ndwi_t1 = np.nan_to_num(indices_t1["ndwi"], nan=-0.5)
    ndwi_t2 = np.nan_to_num(indices_t2["ndwi"], nan=-0.5)

    water_t1, thresh_t1 = optical_predict(ndwi_t1, jrc_arr, wc_arr)

    # 三态逻辑: NO_DATA / NO_CHANGE / DETECTED
    pipeline_status = {
        "optical_t1_raw_valid_ratio": round(float(t1_raw_valid), 4),
        "optical_t2_raw_valid_ratio": round(float(t2_raw_valid), 4),
        "common_valid_ratio": round(float(common_valid_ratio), 4),
        "change_detection_executed": False,
        "optical_status": "not_executed",
    }

    VALID_THRESHOLD = 0.3  # 有效像元低于此阈值视为数据不足
    t2_is_valid = t2_raw_valid > VALID_THRESHOLD

    if not t2_is_valid:
        print(f"\n[5a/7] ChangeDetector — 跳过: T2 有效像元率 {t2_raw_valid:.1%} < {VALID_THRESHOLD:.0%} (云覆盖)")
        print(f"  状态: NO_DATA — 光学双时相变化检测无法执行")
        water_t2 = np.full_like(water_t1, 255, dtype=np.uint8)  # 255 = nodata for uint8
        change = {
            "water_gain": np.zeros_like(water_t1, dtype=np.uint8),
            "water_loss": np.zeros_like(water_t1, dtype=np.uint8),
            "change_score": np.zeros_like(ndwi_t1, dtype=np.float32),
            "change_mask": np.zeros_like(water_t1, dtype=np.uint8),
            "stats": {"gain_pixels": 0, "loss_pixels": 0, "total_changed": 0},
        }
        pipeline_status["optical_status"] = "no_data"
    else:
        water_t2, thresh_t2 = optical_predict(ndwi_t2, jrc_arr, wc_arr)
        print("\n[5a/7] ChangeDetector — 两期光学变化检测")
        change = detect_change(water_t1, water_t2, ndwi_t1=ndwi_t1, ndwi_t2=ndwi_t2)
        pipeline_status["change_detection_executed"] = True
        pipeline_status["optical_status"] = "no_change" if change["stats"]["total_changed"] == 0 else "detected"

    # ── Step 5b: SAR Pipeline (P0-2) ──────────────────────────
    print("\n[5b/7] SAR Pipeline — S1 双时相水体检测")
    s1_t1_reproj = reproject_to_target(s1_t1)
    s1_t2_reproj = reproject_to_target(s1_t2)

    # SAR 统计信息
    sar_stats_t1 = compute_sar_stats(s1_t1_reproj)
    sar_stats_t2 = compute_sar_stats(s1_t2_reproj)
    print(f"  S1 T1 VH: {sar_stats_t1.get('vh',{}).get('mean_db','N/A'):} dB")
    print(f"  S1 T2 VH: {sar_stats_t2.get('vh',{}).get('mean_db','N/A'):} dB")

    # 对齐 SAR 到参考网格
    if s1_t1_reproj.width != ref.width or s1_t1_reproj.height != ref.height:
        s1_t1_reproj = resample_to_grid(s1_t1_reproj, ref)
    if s1_t2_reproj.width != ref.width or s1_t2_reproj.height != ref.height:
        s1_t2_reproj = resample_to_grid(s1_t2_reproj, ref)

    # SAR 水体检测
    sar_water_t1, sar_thresh_t1 = sar_predict(s1_t1_reproj.array[s1_t1_reproj.bands.index("vh")])
    sar_water_t2, sar_thresh_t2 = sar_predict(s1_t2_reproj.array[s1_t2_reproj.bands.index("vh")])

    # SAR 变化检测
    print("\n[5c/7] SAR ChangeDetector — 两期 SAR 变化检测")
    sar_change = detect_change(
        sar_water_t1, sar_water_t2,
        ndwi_t1=s1_t1_reproj.array[s1_t1_reproj.bands.index("vh")],
        ndwi_t2=s1_t2_reproj.array[s1_t2_reproj.bands.index("vh")],
    )

    # ── Step 5d: Fusion — SAR 为主 + 光学辅助 ────────────────
    print("\n[5d/7] Fusion — SAR 为主 + 光学辅助")
    opt_water_t1_for_fusion = water_t1 if pipeline_status["optical_status"] != "not_executed" else None
    opt_water_t2_for_fusion = water_t2 if pipeline_status.get("optical_status") not in ("not_executed", "no_data") else None

    fused = fuse_water_extent(
        sar_water_t1, sar_water_t2,
        optical_water_t1=opt_water_t1_for_fusion,
        sar_confidence=0.8, optical_confidence=0.6,
    )
    pipeline_status["sar_status"] = "success"
    pipeline_status["fusion_status"] = "success"
    pipeline_status["change_candidates"] = int(fused["change_mask"].sum())

    # 使用融合结果作为最终输出
    change = {
        "water_gain": fused["gain"],
        "water_loss": fused["loss"],
        "change_mask": fused["change_mask"],
        "change_score": fused["confidence_map"],
        "stats": {
            "gain_pixels": int(fused["gain"].sum()),
            "loss_pixels": int(fused["loss"].sum()),
            "total_changed": int(fused["change_mask"].sum()),
        },
    }
    water_t1_final = fused["water_t1"]
    water_t2_final = fused["water_t2"]

    # ── Step 6: Polygonizer + ProductWriter ──────────────────
    print("\n[6/7] Polygonizer + ProductWriter — 输出")
    transform = ref.transform
    crs = ref.crs

    features = polygonize_change_mask(
        change["change_mask"], transform, crs,
        min_area_m2=500, pixel_area_m2=100,
    )
    features = assign_change_type(features, water_t1, water_t2)

    # 写 GeoTIFF
    write_geotiff(water_t1_final, PRODUCTS_DIR / "water_mask_t1.tif", crs, transform,
                  bands=["water_mask"], dtype="uint8")
    write_geotiff(water_t2_final, PRODUCTS_DIR / "water_mask_t2.tif", crs, transform,
                  bands=["water_mask"], dtype="uint8")
    write_geotiff(sar_water_t1, PRODUCTS_DIR / "sar_water_mask_t1.tif", crs, transform,
                  bands=["sar_water"], dtype="uint8")
    write_geotiff(sar_water_t2, PRODUCTS_DIR / "sar_water_mask_t2.tif", crs, transform,
                  bands=["sar_water"], dtype="uint8")
    write_geotiff(change["change_mask"], PRODUCTS_DIR / "water_change_mask.tif",
                  crs, transform, bands=["change_mask"], dtype="uint8")
    write_geotiff(change["change_score"], PRODUCTS_DIR / "water_change_score.tif",
                  crs, transform, bands=["change_score"])
    write_geotiff(np.stack([ndwi_t1, ndwi_t2]),
                  PRODUCTS_DIR / "ndwi_composite.tif", crs, transform,
                  bands=["ndwi_t1", "ndwi_t2"])

    # DetectionResult (SAR 为主)
    detection_results = []
    if change["stats"]["total_changed"] > 0:
        sar_features = polygonize_change_mask(
            change["change_mask"], transform, crs,
            min_area_m2=500, pixel_area_m2=100,
        )
        sar_features = assign_change_type(sar_features, water_t1_final, water_t2_final)
        for feat in sar_features:
            dr = {
                "detection_id": f"SAR-{feat['properties']['feature_id']}",
                "source_type": "sentinel_1",
                "source_assets": ["s1_t1", "s1_t2"],
                "task_type": "water_extent_change",
                "category": "water_extent_change_candidate",
                "geometry": feat["geometry"],
                "observed_at": "2026-05~06",
                "confidence": feat["properties"]["confidence"],
                "score_type": "rule_based",
                "model": {"name": "sar_vh_otsu_baseline", "version": "0.1.0"},
                "evidence_refs": [
                    "sar_water_mask_t1.tif", "sar_water_mask_t2.tif",
                    "water_change_mask.tif", "water_change_score.tif",
                ],
                "properties": {
                    "area_m2": feat["properties"]["area_m2"],
                    "change_type": feat["properties"]["change_type"],
                    "data_level": "public_observation_and_model_derived",
                    "pipeline": "sar_primary_fusion",
                },
            }
            detection_results.append(dr)
    else:
        sar_features = []

    write_geojson(sar_features, PRODUCTS_DIR / "anomaly_candidates.geojson")
    write_jsonl(detection_results, PRODUCTS_DIR / "detection_results.jsonl")

    # 预览图
    for name, arr in [("ndwi_t1", ndwi_t1), ("ndwi_t2", ndwi_t2),
                      ("change_mask", change["change_mask"])]:
        write_preview(arr, PRODUCTS_DIR / f"preview_{name}.png")

    # Pipeline 运行报告
    run_report = {
        "run_id": f"RUN-CQ-20260723-{datetime.now().strftime('%H%M%S')}",
        "pipeline_version": "0.3.0",
        "target_crs": "EPSG:4545",
        "resolution_m": 10,
        "inputs": {
            "s2_t1": str(RAW_DIR / "s2_t1.tif"),
            "s2_t2": str(RAW_DIR / "s2_t2.tif"),
            "s1_t1": str(RAW_DIR / "s1_t1.tif"),
            "s1_t2": str(RAW_DIR / "s1_t2.tif"),
            "dem": str(RAW_DIR / "dem_glo30.tif"),
            "jrc": str(RAW_DIR / "jrc_water_occurrence.tif"),
            "worldcover": str(RAW_DIR / "worldcover_2021.tif"),
        },
        "quality": pipeline_status,
        "outputs": {
            "change_candidates": len(sar_features),
            "detection_results": len(detection_results),
        },
        "stages": {
            "optical": pipeline_status["optical_status"],
            "sar": "success",
            "fusion": "success",
            "polygonize": "success" if len(sar_features) > 0 else "no_candidates",
        },
        "warnings": [],
        "errors": [],
    }
    with open(PRODUCTS_DIR / "run_report.json", "w", encoding="utf-8") as f:
        json.dump(run_report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"  Pipeline 运行完成")
    print(f"  输出目录: {PRODUCTS_DIR}")
    print(f"  输出 CRS: EPSG:4545")
    print(f"  光学状态: {pipeline_status['optical_status']}")
    print(f"  SAR 状态: success")
    print(f"  变化图斑: {len(sar_features)} 个")
    print(f"  DetectionResults: {len(detection_results)} 条")
    print(f"  运行报告: run_report.json")
    print("=" * 60)


if __name__ == "__main__":
    main()

