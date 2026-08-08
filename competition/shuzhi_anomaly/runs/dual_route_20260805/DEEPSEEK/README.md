# 512px Short Screen — reviewed_v2 · Fold1+3 (DEEPSEEK route)

**Date**: 2026-08-05 · **Worker**: deepseek_worker (isolated worktree run)
**Question**: Does a 512px continuation of the 448px reviewed_v2 champion beat the
448 baseline on the same 571 OOF samples (fold1=288 + fold3=283)?

**Answer: NO — gate FAIL. Do NOT replace the 448 champion; do NOT complete Fold0/Fold2.**

## 1. Experiment contract (only image_size changed)

| Setting | 448 champion | 512 screen |
|---|---|---|
| image_size | 448 | **512 (only change)** |
| labels | reviewed_v2 | reviewed_v2 (same `train_reviewed_v2.json`) |
| architecture | ConvNeXt-Tiny (hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384) | same |
| init | 384 reviewed_v2 best.pt | 448 champion `shuzhi_platform_inference_v1_2/weights/fold{N}_best.pt` |
| freeze | last_stage | last_stage |
| loss / sampler | CE (ls=0, logit_adj=0) / standard | same |
| lr | backbone 5e-6, head 5e-5 | same |
| epochs / early stop | 10 / patience 3 | same (stopped at epoch 4 both folds) |
| selection | weighted_f1 (best.pt per epoch) | same |
| augmentation | ResizePad + RandomHFlip(0.5) + ColorJitter | same (ResizePad size=512) |
| batch | 8 | **4 (8GB VRAM, recorded; 512 inference peak 296 MiB @ bs4)** |
| workers / seed / AMP / grad clip | 0 / 42 / on / 1.0 | same |

Trainer: `train_classifier.py` (tracked, same script that produced the champion).
Data: `internal_cv_duplicate_near_4fold.csv` splits; OOF val rows exactly the same
288/283 filenames as the baseline CSV.

## 2. Preflight (checkpoint / pipeline reuse evidence)

- champion fold1/fold3 SHA256 match `shuzhi_platform_inference_v1_2/checksums.sha256`
  (fold1 `5b993f…d332d3`, fold3 `80c281…3ad3db`) — see `preflight_checkpoint.json`.
- Champion fold1 checkpoint reproduces the canonical 448 OOF **288/288** predictions
  on fold1 (end-to-end data/transform/pipeline check).
- 512px forward at batch 4: peak 295.5 MiB (inference), training fits 8GB comfortably.
- Baseline recomputed independently on the 571 rows:
  Weighted F1 = **0.985183094035471**, mIoU = **0.654638136686009** (fold1 0.9896465315/0.6549169860,
  fold3 0.9806467333/0.6542585784) — see `baseline_571_verify.json`.

## 3. Results (paired, same 571 samples, reviewed_v2 truth)

| fold | n | baseline_wf1 | 512_wf1 | Δwf1 | baseline_mIoU | 512_mIoU | 乱堆F1 448→512 | 乱占F1 448→512 | 浮漂Recall 448→512 | err 448→512 | changed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 288 | 0.989647 | 0.989647 | 0.0 | 0.654917 | 0.654917 | 1.0 → 1.0 | 0.9655 → 0.9655 | 1.0 → 1.0 | 2 → 2 | 0 |
| 3 | 283 | 0.980647 | 0.977113 | -0.003534 | 0.654259 | 0.598703 | 1.0 → 0.9091 | 0.9697 → 0.9697 | 0.9960 → 0.9960 | 4 → 5 | 1 |
| combined | 571 | 0.985183 | 0.983432 | -0.001751 | 0.654638 | 0.626860 | 1.0 → 0.9565 | 0.9677 → 0.9677 | 0.9981 → 0.9981 | 6 → 7 | 1 |

- fold1 reproduced the baseline exactly (0 changed predictions).
- fold3 regressed: the only prediction change is **02122.jpg (true 乱堆) 448→乱堆, 512→乱采**
  (fold3 乱堆 recall 1.0→0.8333). Full list in `changed_predictions.csv`.

## 4. Gate decision (`gate_decision.json`)

| Criterion | Required | 512 value | Pass |
|---|---|---|---|
| Weighted F1 | > 0.9851830940 | 0.983432 | **FAIL** |
| mIoU | >= 0.6546381367 | 0.626860 | **FAIL** |
| 乱堆 F1 | not decreased | 1.0 → 0.956522 | **FAIL** |
| 乱占 F1 | drop <= 0.01 | 0.967742 (=) | pass |
| 有漂浮物 Recall | drop <= 0.002 | 0.998051 (=) | pass |

`gate_pass = false` — 3/5 criteria failed. Per protocol, **Fold0/Fold2 were NOT run**.

## 5. Verdict & next steps

- 512px continuation does **not** beat the 448 champion on the 571-sample screen
  (fold1 tie + fold3 regression: wf1 -0.0035, mIoU -0.0556, one 乱堆→乱采 flip).
- **Not worth completing the four-fold 512 run**; keep the 448px reviewed_v2 champion
  (platform score 86.34) as the reference.
- If resolution gains are still wanted later, the failure mode (乱堆 confusion at
  512 with champion init, 10-epoch continuation) suggests testing fresh 512 training
  from the 384 reviewed_v2 checkpoints, or a longer schedule — NOT in this screen.

## 6. Artifacts

- `fold1/`, `fold3/`: `best.pt`, `last.pt`, `oof_predictions.csv`, `best_metrics.json`,
  `run_config.json`, `history.json`, `confusion_matrix.csv`
- `paired_metrics.csv`, `changed_predictions.csv`, `gate_decision.json`,
  `baseline_571_verify.json`, `preflight_checkpoint.json`
- `logs/fold1.{out,err}.log`, `logs/fold3.{out,err}.log`
- Scripts: `run_screen_fold.ps1`, `screen_gpu_lock.py`, `verify_baseline_571.py`,
  `compute_paired_metrics.py` (copies also kept under the isolated worktree)

**GPU / runtime**: RTX 2070 Max-Q 8GB (WDDM, compute idle before launch; shared
`gpu.lock` protocol with route C). fold1: early-stop epoch 4 (best epoch 1), fold3:
early-stop epoch 4 (best epoch 1). ~11 min per fold incl. eval. batch_size=4.