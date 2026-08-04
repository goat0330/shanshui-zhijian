"""Create compact CPU-side OOF error tables for manual review."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")
MINORITY = {"乱采", "乱建", "乱堆", "乱占", "正常"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def probability(row: dict[str, str], label: str) -> float:
    return float(row[f"prob_{label}"])


def enrich(row: dict[str, str]) -> dict[str, object]:
    probabilities = sorted(
        ((probability(row, label), label) for label in LABELS), reverse=True
    )
    pred_probability = probability(row, row["pred_label"])
    true_probability = probability(row, row["true_label"])
    return {
        **row,
        "true_probability": true_probability,
        "pred_probability": pred_probability,
        "margin": probabilities[0][0] - probabilities[1][0],
        "confidence": probabilities[0][0],
        "is_error": row["true_label"] != row["pred_label"],
        "scene_id": "",
        "nearest_train_image": "",
        "review_status": "pending",
    }


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--oof",
        type=Path,
        default=Path("runs/repair_v2/global_oof/combined_oof_predictions.csv"),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("runs/repair_v2/global_oof/analysis")
    )
    args = parser.parse_args()
    rows = [enrich(row) for row in read_rows(args.oof)]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    metrics: list[dict[str, object]] = []
    for label in LABELS:
        support = sum(row["true_label"] == label for row in rows)
        predicted = sum(row["pred_label"] == label for row in rows)
        tp = sum(row["true_label"] == label and row["pred_label"] == label for row in rows)
        fp = sum(row["true_label"] != label and row["pred_label"] == label for row in rows)
        fn = sum(row["true_label"] == label and row["pred_label"] != label for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
        metrics.append({"class": label, "support": support, "predicted_count": predicted, "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1, "iou": iou})
    write_csv(args.out_dir / "per_class_metrics.csv", metrics, list(metrics[0]))

    minority = [row for row in rows if row["true_label"] in MINORITY]
    minority_fields = ["filename", "fold", "true_label", "pred_label", "true_probability", "pred_probability", "margin", "scene_id", "nearest_train_image", "review_status", "is_error"]
    write_csv(args.out_dir / "minority_error_census.csv", minority, minority_fields)

    review_fields = ["filename", "fold", "true_label", "pred_label", "true_probability", "pred_probability", "confidence", "margin", "is_error"]
    errors = [row for row in rows if row["is_error"]]
    write_csv(args.out_dir / "low_confidence_samples.csv", sorted(rows, key=lambda row: (row["confidence"], row["filename"])), review_fields)
    write_csv(args.out_dir / "small_margin_samples.csv", sorted(rows, key=lambda row: (row["margin"], row["filename"])), review_fields)
    write_csv(args.out_dir / "high_confidence_errors.csv", sorted(errors, key=lambda row: (-row["confidence"], row["filename"])), review_fields)

    summary = {
        "oof_rows": len(rows),
        "errors": len(errors),
        "non_floating_predicted_as_floating": sum(row["true_label"] != "有漂浮物" and row["pred_label"] == "有漂浮物" for row in rows),
        "outputs": ["per_class_metrics.csv", "minority_error_census.csv", "low_confidence_samples.csv", "small_margin_samples.csv", "high_confidence_errors.csv"],
    }
    (args.out_dir / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
