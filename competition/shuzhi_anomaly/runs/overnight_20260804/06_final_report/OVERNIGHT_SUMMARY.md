# Overnight 20260804 — Shuzhi Anomaly Classifier Summary

Run date: 2026-08-04 02:30–03:40 (+08) | Lead session: ses_037229559ffeXuWP1YVcFSn0Br | Git: 24368ce2

## Goal
reviewed_v2 4-fold continuation training, strict scene-holdout risk assessment, 448px single-fold diagnostic, candidate selection and test inference, under hard constraints (never overwrite champion `runs/repair_v2/fold*_last_stage/best.pt`, all artifacts under `runs/overnight_20260804/`, single CUDA process, no forbidden methods).

## 1. Preflight (`00_preflight/`)
- GPU: RTX 2070 Max-Q 8GB, driver 592.82, CUDA 13.1 (toolkit 11.8), 54°C, 6.9GB free at start.
- Python 3.11.5 / torch 2.6.0+cu118 / timm 1.0.28; CUDA available.
- Champion checkpoints verified intact (4 SHAs match; `champion_checkpoint_check.json`).
- reviewed_v2 strict review CSV **PASSED**: `strictly valid completed review CSV: 11 rows; relabels=2` (00033 正常→有漂浮物, 02111 正常→乱堆). Full env in `environment_report.json`.

## 2. CPU workers (3, own worktrees, CPU-only)
- **A** `04_oof_compare/`: raw_v1_metrics.json (wf1=0.979403, errors=18), reviewed_v2_existing_predictions_metrics.json (wf1=0.982022, errors=16), label_change_impact.csv. ✅ merged.
- **B** `04_oof_compare/error_transition.csv` + summary: net error −1, resolved=1 (00020.jpg), new=0, persistent=15 (compared under reviewed_v2 truth). ✅ merged.
- **C** `02_scene_holdout_block0005/`: strict holdout manifest (holdout=801 block0005, train=343), class_stats, risk_report → verdict: block is 99.9% single-class, fold-overlap leakage → diagnostic-only, never primary. ✅ merged.

## 3. Experiment 01 — reviewed_v2 4-fold continuation (`01_reviewed_v2_4fold/`)
Each fold init from champion `repair_v2/fold*_last_stage/best.pt`, convnext_tiny_384, last_stage, backbone-lr 5e-6, head-lr 5e-5, wd 0.05, ls 0, logit-adj 0, sampler standard, epochs 10, patience 3, batch 16, AMP, clip 1, seed 42, workers 2, selection weighted_f1.

| Fold | New wf1 | Champion wf1 | Δ | Errors | Notes |
|------|--------|--------------|------|--------|-------|
| 0 | 0.983987 | 0.983987 | 0 | 4 | identical |
| 1 | 0.989647 | 0.989647 | 0 | 2 | identical |
| 2 | 0.980900 | 0.970707 | **+0.010** | 4 | rescued 00033/02111 relabels |
| 3 | 0.976883 | 0.973410 | +0.003 | 5 (champ 6) | resolved 00020 |

No NaN/Inf; checkpoints written; no fold dropped. Per-fold `stage_result.json` saved.

## 4. Global OOF gate (`04_oof_compare/`)
- raw_v1 champion: wf1=0.979403, mIoU=0.6295, errors=18.
- reviewed_v2 continuation: **wf1=0.982875 (≥0.979403 → GATE PASS)**, mIoU=0.6391, errors=15, floating recall 0.9990 (vs 0.9980).
- Decision: reviewed_v2 is a valid candidate (B). Champion mainline retained as candidate A.

## 5. file_block_0005 strict Holdout (`02_scene_holdout_block0005/`)
Diagnostic only. Holdout val=801 (99.9% 有漂浮物, baseline 0.9988), train=343. wf1=0.9969 inflated by majority; macro-f1=0.166; 3 errors. **Not representative; NOT used as primary; mainline untouched.**

## 6. 448px single-fold diagnostic (`03_resolution448_fold/`)
Fold 2 (contains 乱建+正常). 448px from 384 fold2 best, batch 8, workers 0. wf1=0.984405 (vs 0.980900 at 384), errors 4→3, resolved 02044. **Extension recommended** but not executed overnight (time window).

## 7. Test inference (`05_test_inference/`)
Candidate B (reviewed_v2) only — passed gate. Equal-weight 4-fold softmax average, no threshold/bias.
- `submission_reviewed_v2.json` (695) — validate_submission.py **valid=true**, six-class labels, 691 JPG + 4 PNG, no dup/missing.
- `test_probabilities_reviewed_v2.csv` (695).
- SHAs recorded in `CHECKPOINT_SHA256.txt`.

## 8. Final outputs (`06_final_report/`)
- `OVERNIGHT_SUMMARY.md`, `metrics_comparison.csv`, `environment_report.json`, `CHECKPOINT_SHA256.txt`.

## Constraints honored
✅ Champion checkpoints untouched (SHA-verified post-run). ✅ All new artifacts under `runs/overnight_20260804/`. ✅ Single CUDA training process at a time (sequential queue). ✅ No class_sequence / full class-balance / Focal / Logit Adjustment / MOSS-VL / YOLO. ✅ No test pseudo-labels. ✅ raw train.json/raw_v1/reviewed_v1 unmodified.

## Recommended next actions
1. Promote reviewed_v2 4-fold as candidate submission (`submission_reviewed_v2.json`); compare with champion `submission_b0.json` on any held-out leaderboard.
2. Run full 4-fold 448px extension (recommended by stage 6) under a fresh overnight window.
3. Convert test_probabilities CSV → team submission format and run an A/B vote between champion and reviewed_v2.
