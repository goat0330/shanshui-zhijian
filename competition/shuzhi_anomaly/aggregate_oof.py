"""Combine best-epoch fold OOF CSV files and compute global OOF metrics."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from classification_common import (
    LABELS,
    confusion_matrix_from_ids,
    json_ready,
    metrics_from_confusion,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        type=Path,
        nargs="+",
        help="Fold directories or explicit oof_predictions.csv paths.",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=1139)
    return parser.parse_args()


def resolve_input(path: Path) -> Path:
    return path / "oof_predictions.csv" if path.is_dir() else path


def main() -> int:
    args = parse_args()
    rows: list[dict[str, str]] = []
    for supplied in args.inputs:
        path = resolve_input(supplied.resolve())
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))

    filenames = [row["filename"] for row in rows]
    duplicates = sorted({name for name in filenames if filenames.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate OOF filenames: {duplicates[:20]}")
    if args.expected_count and len(rows) != args.expected_count:
        raise ValueError(
            f"OOF count mismatch: got {len(rows)}, expected {args.expected_count}"
        )
    y_true = [int(row["true_label_id"]) for row in rows]
    y_pred = [int(row["pred_label_id"]) for row in rows]
    matrix = confusion_matrix_from_ids(y_true, y_pred)
    metrics = metrics_from_confusion(matrix)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with (out_dir / "combined_oof_predictions.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (int(row["fold"]), row["filename"])))
    (out_dir / "global_oof_metrics.json").write_text(
        json.dumps(json_ready(metrics), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "global_confusion_matrix.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\pred", *LABELS])
        for label, row in zip(LABELS, metrics["confusion_matrix"]):
            writer.writerow([label, *row])
    print(json.dumps(json_ready(metrics), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
