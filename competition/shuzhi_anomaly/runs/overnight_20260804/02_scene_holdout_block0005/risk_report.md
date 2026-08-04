# Risk Report: strict scene-holdout for file_block_0005

## Summary

- Label source: `generated/train_reviewed_v2.json` (1144 records, authoritative for train).
- Label order (6 classes): 乱采 / 乱建 / 乱堆 / 乱占 / 有漂浮物 / 正常
- Scene group: `file_block_0005` (contiguous filename block).
- **val_holdout size: 801** (all train-labeled images with sequence_id == file_block_0005).
- **train size: 343** (all other reviewed train images; 0 overlap with holdout, verified).
- manifest train total = 1144 = reviewed records = train_index records (consistent).

## Holdout class distribution

| class | holdout n | holdout %% | full-train n | full-train %% | train(others) n |
|---|---|---|---|---|---|
| 乱采 | 0 | 0.0 | 24 | 2.1 | 24 |
| 乱建 | 0 | 0.0 | 4 | 0.3 | 4 |
| 乱堆 | 0 | 0.0 | 24 | 2.1 | 24 |
| 乱占 | 0 | 0.0 | 60 | 5.2 | 60 |
| 有漂浮物 | 800 | 99.9 | 1027 | 89.8 | 227 |
| 正常 | 1 | 0.1 | 5 | 0.4 | 4 |

Constant-predict-most-frequent baseline (reviewed_v2 labels):
- val_holdout: predict `有漂浮物` -> acc = 0.9988 (800/801)
- train(others): predict `有漂浮物` -> acc = 0.6618 (227/343)

## Risks

1. **Severe class imbalance in the holdout.** The holdout contains only 2 classes: 有漂浮物 = 800 (99.9%), 正常 = 1 (0.1%). The other 4 classes (乱采/乱建/乱堆/乱占) have ZERO holdout examples. Validation metrics on this holdout are dominated by a single class; any model can exceed ~99.9% accuracy by predicting the majority class.

2. **Representativeness.** The holdout class mix (99.9% majority class) differs sharply from the full train set (majority class `有漂浮物` at 89.8% across all 1144 reviewed images), so holdout accuracy is NOT a good estimator of full-train accuracy.

3. **Fold overlap (weakens per-fold comparison).** Holdout filenames fall across 4 of the 4 internal-CV folds: fold0=195, fold1=203, fold2=204, fold3=199. A strict-holdout model CANNOT be compared fold-by-fold against the existing 4-fold CV: each CV fold's validation set leaks the same scene block, so per-fold numbers are not independent.

## RECOMMENDATION

**NOT safe as a primary risk-assessment.**

A strict file_block_0005 holdout is **not a reliable risk-assessment** and must not replace the main line, because:

- The holdout is a near-single-class scene block (one dominant class + one rare second class). Accuracy and per-class metrics on it are dominated by class bias, not model skill.
- 4 of 6 classes are entirely absent from validation, so rare-class behavior (the actual monitoring targets: 乱采/乱建/乱堆/乱占) is unmeasurable.
- Holdout images are spread across the existing 4 CV folds, so no fold-vs-holdout comparison is statistically valid.
- A model trained on the non-holdout data would still have seen file_block_0005-like scenes inside those CV folds, so the diagnostic is not a true generalization check.

**If the diagnostic is still desired**, treat it strictly as a single-scene robustness probe: report the constant-predict baseline (0.9988) next to model accuracy, report per-class numbers per the 2 present classes only, and never mix it with the 4-fold internal CV. Do not use its accuracy as an estimate of leaderboard/test performance.
