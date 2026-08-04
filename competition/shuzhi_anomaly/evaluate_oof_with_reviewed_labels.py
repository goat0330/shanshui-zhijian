"""Re-score frozen OOF predictions under the confirmed reviewed-v2 labels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oof", type=Path, default=Path("runs/repair_v2/global_oof/combined_oof_predictions.csv"))
    parser.add_argument("--decisions", type=Path, default=Path("review_11_minority_v1/review_decisions_v2.csv"))
    parser.add_argument("--output", type=Path, default=Path("generated/reviewed_v2_oof_metrics.json"))
    parser.add_argument("--confusion-output", type=Path, default=Path("generated/reviewed_v2_oof_confusion_matrix.csv"))
    args = parser.parse_args()

    oof = read_csv(args.oof)
    decisions = {row["filename"]: row for row in read_csv(args.decisions)}
    adjusted = []
    changed = []
    for row in oof:
        decision = decisions.get(row["filename"])
        true_label = row["true_label"]
        if decision:
            if decision["official_label"] != true_label:
                raise ValueError(f"official label mismatch: {row['filename']}")
            true_label = decision["reviewed_label"]
            if true_label != row["true_label"]:
                changed.append(row["filename"])
        adjusted.append((true_label, row["pred_label"]))

    matrix = [[0 for _ in LABELS] for _ in LABELS]
    for true_label, pred_label in adjusted:
        matrix[LABELS.index(true_label)][LABELS.index(pred_label)] += 1
    total = len(adjusted)
    per_class = {}
    f1_values = []
    iou_values = []
    supports = []
    for index, label in enumerate(LABELS):
        tp = matrix[index][index]
        fp = sum(matrix[row][index] for row in range(len(LABELS)) if row != index)
        fn = sum(matrix[index][col] for col in range(len(LABELS)) if col != index)
        support = sum(matrix[index])
        predicted = sum(matrix[row][index] for row in range(len(LABELS)))
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
        per_class[label] = {"support": support, "predicted_count": predicted, "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1, "iou": iou}
        f1_values.append(f1)
        iou_values.append(iou)
        supports.append(support)
    metrics = {
        "label_source": "reviewed_v2_confirmed_11_only",
        "oof_rows": total,
        "changed_truth_rows": changed,
        "accuracy": sum(matrix[i][i] for i in range(len(LABELS))) / total,
        "weighted_f1": sum(f1 * support for f1, support in zip(f1_values, supports)) / total,
        "macro_f1": sum(f1_values) / len(LABELS),
        "balanced_accuracy": sum(per_class[label]["recall"] for label in LABELS) / len(LABELS),
        "mIoU": sum(iou_values) / len(LABELS),
        "per_class": per_class,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with args.confusion_output.resolve().open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true_label"] + list(LABELS))
        writer.writerows([[label] + matrix[index] for index, label in enumerate(LABELS)])
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
