"""Evaluate no-training baselines on the same internal CV folds."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def classification_metrics(true_labels: list[str], predicted: list[str]) -> dict[str, object]:
    rows = []
    total = len(true_labels)
    for label in LABELS:
        tp = sum(true == label and pred == label for true, pred in zip(true_labels, predicted))
        support = sum(true == label for true in true_labels)
        predicted_count = sum(pred == label for pred in predicted)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        union = support + predicted_count - tp
        iou = tp / union if union else 0.0
        rows.append({"label": label, "support": support, "precision": precision,
                     "recall": recall, "f1": f1, "iou": iou})
    accuracy = sum(true == pred for true, pred in zip(true_labels, predicted)) / total if total else 0.0
    weighted_f1 = sum(row["f1"] * row["support"] for row in rows) / total if total else 0.0
    return {
        "accuracy": accuracy,
        "weighted_f1": weighted_f1,
        "macro_f1": sum(row["f1"] for row in rows) / len(LABELS),
        "miou": sum(row["iou"] for row in rows) / len(LABELS),
        "per_class": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cv-manifest", type=Path,
                        default=Path("competition/shuzhi_anomaly/generated/internal_cv_duplicate_near_4fold.csv"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rows = read_csv(args.cv_manifest.resolve())
    folds = sorted({int(row["fold"]) for row in rows})
    results: list[dict[str, object]] = []
    global_true: dict[str, list[str]] = {}
    global_predicted: dict[str, list[str]] = {}
    for fold in folds:
        validation = [row for row in rows if int(row["fold"]) == fold]
        training = [row for row in rows if int(row["fold"]) != fold]
        true_labels = [row["label"] for row in validation]
        train_counts = Counter(row["label"] for row in training)
        rng = random.Random(args.seed + fold)
        predictions = {
            "B0_all_floating": ["有漂浮物"] * len(validation),
            "B1_train_prior_random": rng.choices(
                LABELS, weights=[train_counts[label] for label in LABELS], k=len(validation)
            ),
            "B2_uniform_random": [rng.choice(LABELS) for _ in validation],
        }
        for baseline, predicted in predictions.items():
            metrics = classification_metrics(true_labels, predicted)
            results.append({"baseline": baseline, "fold": fold, **metrics})
            global_true.setdefault(baseline, []).extend(true_labels)
            global_predicted.setdefault(baseline, []).extend(predicted)

    for baseline in sorted(global_true):
        metrics = classification_metrics(global_true[baseline], global_predicted[baseline])
        results.append({"baseline": baseline, "fold": "global_oof", **metrics})

    output_dir = args.cv_manifest.resolve().parent
    output_json = output_dir / "constant_baselines_duplicate_near_4fold.json"
    output_json.write_text(json.dumps({"seed": args.seed, "results": results},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_csv = output_dir / "constant_baselines_duplicate_near_4fold.csv"
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("baseline", "fold", "accuracy", "weighted_f1", "macro_f1", "miou"))
        writer.writeheader()
        for row in results:
            writer.writerow({key: row[key] for key in writer.fieldnames})
    print(json.dumps({"output_json": str(output_json), "output_csv": str(output_csv),
                      "folds": folds}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
