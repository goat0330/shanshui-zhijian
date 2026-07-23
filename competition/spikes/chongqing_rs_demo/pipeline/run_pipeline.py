#!/usr/bin/env python3
"""
山水智鉴 V0 Pipeline — 一键运行全链

用法:
    python pipeline/run_pipeline.py

数据处理流程:
    InputAdapter → Preprocessor → FeatureExtractor → ModelClient
    → ChangeDetector → Polygonizer → ProductWriter
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
from pipeline.io.reader import read_geotiff, validate_alignment
from pipeline.processing.preprocessor import check_and_report
from pipeline.features.spectral import compute_all_indices
from pipeline.models.baseline_water import predict as water_predict
from pipeline.detection.change import detect_change
from pipeline.postprocessing.polygonize import polygonize_change_mask, assign_change_type
from pipeline.io.writer import write_geotiff, write_geojson, write_jsonl

# ── 路径配置 ──────────────────────────────────────────────────────
DATA_DIR = ROOT / "data" / "chongqing_demo"
RAW_DIR = DATA_DIR / "raw"
PRODUCTS_DIR = Path(__file__).resolve().parent.parent / "products"

# 输入文件
S2_T1_PATH = RAW_DIR / "s2_t1.tif"
S2_T2_PATH = RAW_DIR / "s2_t2.tif"
DEM_PATH = RAW_DIR / "dem_glo30.tif"
JRC_PATH = RAW_DIR / "jrc_water_occurrence.tif"
WC_PATH = RAW_DIR / "worldcover_2021.tif"


def main():
    print("=" * 60)
    print("  山水智鉴 V0 Pipeline")
    print("=" * 60)

    # ── Step 1: InputAdapter ────────────────────────────────────
    print("\n[1/6] InputAdapter — 读取数据")
    s2_t1 = read_geotiff(S2_T1_PATH,
                         bands=["blue", "green", "red", "nir", "swir1", "swir2"])
    s2_t2 = read_geotiff(S2_T2_PATH,
                         bands=["blue", "green", "red", "nir", "swir1", "swir2"])
    jrc = read_geotiff(JRC_PATH, bands=["occurrence"])
    wc = read_geotiff(WC_PATH, bands=["landcover"])

    # ── Step 2: Preprocessor ────────────────────────────────────
    print("\n[2/6] Preprocessor — 对齐检查")
    check_and_report([s2_t1, s2_t2, jrc, wc],
                     labels=["S2_T1", "S2_T2", "JRC", "WorldCover"])

    # 重采样 JRC (30m→10m 网格) 和 WorldCover 到 S2 网格
    # 注意: GEE 导出时已指定 CRS+scale, 此处检查即可
    assert s2_t1.width == s2_t2.width and s2_t1.height == s2_t2.height, \
        "T1 和 T2 尺寸不一致!"
    print("  ✅ 所有数据对齐通过")

    # ── Step 3: FeatureExtractor ────────────────────────────────
    print("\n[3/6] FeatureExtractor — 光谱指数计算")
    indices_t1 = compute_all_indices(s2_t1)
    indices_t2 = compute_all_indices(s2_t2)
    print(f"  NDWI_T1: 均值={indices_t1['ndwi'].mean():.4f}, "
          f"范围=[{indices_t1['ndwi'].min():.4f}, {indices_t1['ndwi'].max():.4f}]")

    # ── Step 4: ModelClient V0 ─────────────────────────────────
    print("\n[4/6] ModelClient — 水体提取")
    jrc_arr = jrc.array[0]
    wc_arr = wc.array[0]

    water_t1, thresh_t1 = water_predict(indices_t1["ndwi"], jrc_arr, wc_arr)
    water_t2, thresh_t2 = water_predict(indices_t2["ndwi"], jrc_arr, wc_arr)

    # ── Step 5: ChangeDetector ─────────────────────────────────
    print("\n[5/6] ChangeDetector — 两期变化检测")
    change = detect_change(
        water_t1, water_t2,
        ndwi_t1=indices_t1["ndwi"],
        ndwi_t2=indices_t2["ndwi"],
    )

    # ── Step 6: Polygonizer + ProductWriter ──────────────────
    print("\n[6/6] Polygonizer + ProductWriter — 输出")
    transform = s2_t1.transform
    crs = s2_t1.crs
    pixel_area = 100.0  # 10m × 10m

    # 变化图斑
    features = polygonize_change_mask(
        change["change_mask"], transform, crs,
        min_area_m2=500, pixel_area_m2=pixel_area,
    )
    features = assign_change_type(features, water_t1, water_t2)

    # 写出
    write_geotiff(water_t1, PRODUCTS_DIR / "water_mask_t1.tif", crs, transform,
                  bands=["water_mask"], dtype="uint8")
    write_geotiff(water_t2, PRODUCTS_DIR / "water_mask_t2.tif", crs, transform,
                  bands=["water_mask"], dtype="uint8")
    write_geotiff(change["change_mask"], PRODUCTS_DIR / "water_change_mask.tif",
                  crs, transform, bands=["change_mask"], dtype="uint8")
    write_geotiff(change["change_score"], PRODUCTS_DIR / "water_change_score.tif",
                  crs, transform, bands=["change_score"])

    # DetectionResult 每个图斑一条
    detection_results = []
    for feat in features:
        dr = {
            "detection_id": feat["properties"]["feature_id"],
            "source_type": "sentinel_2",
            "source_assets": ["s2_t1", "s2_t2"],
            "task_type": "water_extent_change",
            "category": "shoreline_change_candidate",
            "geometry": feat["geometry"],
            "observed_at": "2026-06",
            "confidence": feat["properties"]["confidence"],
            "score_type": "rule_based",
            "model": {
                "name": "ndwi_otsu_change_baseline",
                "version": "0.1.0",
            },
            "evidence_refs": [
                "s2_t1.tif", "s2_t2.tif",
                "water_change_mask.tif", "water_change_score.tif",
            ],
            "properties": {
                "area_m2": feat["properties"]["area_m2"],
                "change_type": feat["properties"]["change_type"],
                "data_level": feat["properties"]["data_level"],
            },
        }
        detection_results.append(dr)

    write_geojson(features, PRODUCTS_DIR / "anomaly_candidates.geojson")
    write_jsonl(detection_results, PRODUCTS_DIR / "detection_results.jsonl")
    write_geotiff(
        np.stack([indices_t1["ndwi"], indices_t2["ndwi"]]),
        PRODUCTS_DIR / "ndwi_composite.tif",
        crs, transform,
        bands=["ndwi_t1", "ndwi_t2"],
    )

    print("\n" + "=" * 60)
    print(f"  ✅ Pipeline 运行完成")
    print(f"  输出目录: {PRODUCTS_DIR}")
    print(f"  DetectionResults: {len(detection_results)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
