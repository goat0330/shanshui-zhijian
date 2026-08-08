# Camera Group v2 reviewed repair

本版本只应用人工复核中明确的同机位/同场景合并，不重新推断标签，不修改原始 manifest 或 Fold。

- full rows: 1839 (train=1144, test=695)
- CV rows: 1834 (active train=1139, test=695)
- v1 groups: 533; v2 groups: 508
- repaired merged components: 10

## Applied repair scope

- critical cross-fold pairs from critical_findings.csv
- train fixed-camera ranges 00759–00768 and 02097–02111
- reviewed test fixed-camera ranges 02163–02175, 02185–02189, 02212–02214, 02295–02296, 02299–02302

## Files

- camera_group_manifest_full.csv: all source rows with v1/v2 provenance
- camera_group_manifest_cv.csv: 1139 active train rows plus 695 test rows for GroupKFold construction
- camera_group_merges.csv: applied reviewed merge records
- camera_group_summary.csv: v2 group membership summary

## Limits

This is a reviewed repair pass, not a full SIFT/ORB reclustering. New group folds must be rebuilt from camera_group_manifest_cv.csv before using OOF as a model-selection metric.
