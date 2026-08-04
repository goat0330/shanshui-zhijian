"""Audit duplicate and provisional-sequence leakage in an internal CV manifest."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def crossing(groups: dict[str, set[int]]) -> list[dict[str, object]]:
    return [
        {"group_id": group_id, "folds": sorted(folds)}
        for group_id, folds in sorted(groups.items())
        if len(folds) > 1
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-dir", type=Path, default=Path("competition/shuzhi_anomaly/generated"))
    parser.add_argument("--cv-manifest", type=Path, default=None)
    args = parser.parse_args()
    generated = args.generated_dir.resolve()
    cv_path = (args.cv_manifest or generated / "internal_cv_duplicate_near_4fold.csv").resolve()
    cv_rows = read_csv(cv_path)
    manifest = {row["filename"]: row for row in read_csv(generated / "data_manifest.csv")}
    fold_by_name = {row["filename"]: int(row["fold"]) for row in cv_rows}

    exact_groups: dict[str, set[int]] = defaultdict(set)
    for row in read_csv(generated / "exact_duplicate_groups.csv"):
        if row["filename"] in fold_by_name:
            exact_groups[row["duplicate_group"]].add(fold_by_name[row["filename"]])
    near_cross_pairs = []
    for row in read_csv(generated / "near_duplicate_candidates.csv"):
        left, right = row["left_filename"], row["right_filename"]
        if left in fold_by_name and right in fold_by_name:
            if fold_by_name[left] != fold_by_name[right]:
                near_cross_pairs.append({"left": left, "right": right,
                                         "left_fold": fold_by_name[left],
                                         "right_fold": fold_by_name[right]})
    sequence_groups: dict[str, set[int]] = defaultdict(set)
    for filename, fold in fold_by_name.items():
        sequence_groups[manifest[filename]["sequence_id"]].add(fold)

    fold_report = {}
    for fold in sorted(set(fold_by_name.values())):
        rows = [row for row in cv_rows if int(row["fold"]) == fold]
        fold_report[str(fold)] = {
            "row_count": len(rows),
            "class_counts": dict(Counter(row["label"] for row in rows)),
            "missing_labels": [label for label in LABELS if not any(row["label"] == label for row in rows)],
            "sequence_group_count": len({manifest[row["filename"]]["sequence_id"] for row in rows}),
            "aspect_ratio_min": min(float(manifest[row["filename"]]["width"]) / float(manifest[row["filename"]]["height"]) for row in rows),
            "aspect_ratio_max": max(float(manifest[row["filename"]]["width"]) / float(manifest[row["filename"]]["height"]) for row in rows),
        }

    report = {
        "cv_manifest": str(cv_path),
        "row_count": len(cv_rows),
        "fold_count": len(fold_report),
        "folds": fold_report,
        "exact_duplicate_cross_fold": crossing(exact_groups),
        "near_duplicate_cross_fold_count": len(near_cross_pairs),
        "near_duplicate_cross_fold_preview": near_cross_pairs[:20],
        "provisional_sequence_cross_fold": crossing(sequence_groups),
        "strict_group_ready": False,
        "note": "Filename sequence blocks are provisional; source scene/video groups are still required for strict Group-OOD CV.",
    }
    output = generated / "cv_audit_duplicate_near_4fold.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "exact_duplicate_cross_fold_count": len(report["exact_duplicate_cross_fold"]),
        "near_duplicate_cross_fold_count": report["near_duplicate_cross_fold_count"],
        "provisional_sequence_cross_fold_count": len(report["provisional_sequence_cross_fold"]),
        "strict_group_ready": report["strict_group_ready"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
