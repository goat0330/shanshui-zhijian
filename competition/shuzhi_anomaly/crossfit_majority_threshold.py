"""Cross-fit a threshold for the majority class without optimistic OOF reuse.

For each held-out fold, the threshold is selected using all *other* folds and
then applied to the held-out fold. Final output remains one of six classes.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from classification_common import (
    LABELS,
    confusion_matrix_from_ids,
    json_ready,
    metrics_from_confusion,
)

MAJORITY_LABEL = "有漂浮物"
MAJORITY_ID = LABELS.index(MAJORITY_LABEL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("oof_csv", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0.40)
    parser.add_argument("--stop", type=float, default=0.99)
    parser.add_argument("--step", type=float, default=0.01)
    return parser.parse_args()


def predict_with_threshold(probabilities: np.ndarray, threshold: float) -> np.ndarray:
    minority = probabilities.copy()
    minority[:, MAJORITY_ID] = -1.0
    minority_prediction = minority.argmax(axis=1)
    return np.where(
        probabilities[:, MAJORITY_ID] >= threshold,
        MAJORITY_ID,
        minority_prediction,
    )


def main() -> int:
    args = parse_args()
    with args.oof_csv.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    probabilities = np.asarray(
        [[float(row[f"prob_{label}"]) for label in LABELS] for row in rows],
        dtype=np.float64,
    )
    targets = np.asarray([int(row["true_label_id"]) for row in rows], dtype=np.int64)
    folds = np.asarray([int(row["fold"]) for row in rows], dtype=np.int64)
    thresholds = np.arange(args.start, args.stop + args.step / 2, args.step)
    crossfit_predictions = np.empty_like(targets)
    choices: list[dict[str, object]] = []

    for held_out_fold in sorted(np.unique(folds).tolist()):
        tune_mask = folds != held_out_fold
        test_mask = folds == held_out_fold
        best_threshold = float(thresholds[0])
        best_score = float("-inf")
        for threshold in thresholds:
            predictions = predict_with_threshold(probabilities[tune_mask], float(threshold))
            metrics = metrics_from_confusion(
                confusion_matrix_from_ids(targets[tune_mask], predictions)
            )
            if float(metrics["weighted_f1"]) > best_score:
                best_score = float(metrics["weighted_f1"])
                best_threshold = float(threshold)
        crossfit_predictions[test_mask] = predict_with_threshold(
            probabilities[test_mask], best_threshold
        )
        choices.append(
            {
                "held_out_fold": held_out_fold,
                "selected_threshold": best_threshold,
                "tuning_weighted_f1": best_score,
            }
        )

    metrics = metrics_from_confusion(
        confusion_matrix_from_ids(targets, crossfit_predictions)
    )
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"threshold_choices": choices, "crossfit_metrics": metrics}
    (out_dir / "crossfit_majority_threshold.json").write_text(
        json.dumps(json_ready(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_rows: list[dict[str, str]] = []
    for row, pred_id in zip(rows, crossfit_predictions.tolist()):
        updated = dict(row)
        updated["threshold_pred_label_id"] = str(pred_id)
        updated["threshold_pred_label"] = LABELS[pred_id]
        output_rows.append(updated)
    with (out_dir / "crossfit_threshold_predictions.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)
    print(json.dumps(json_ready(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
