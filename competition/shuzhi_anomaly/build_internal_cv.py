"""Build a non-destructive internal CV manifest for the six-class classifier.

The released classification data has no official labeled validation split. This
script creates fold assignments from labeled training rows only. The default
mode keeps exact/near-duplicate components together and is suitable for a
Competition-IID-style internal check. ``provisional_sequence`` is an explicit
ablation only until real video/source groups are confirmed.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")


class UnionFind:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generated-dir",
        type=Path,
        default=Path("competition/shuzhi_anomaly/generated"),
    )
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--group-mode",
        choices=("duplicate_near", "provisional_sequence"),
        default="duplicate_near",
    )
    parser.add_argument(
        "--allow-provisional",
        action="store_true",
        help="Allow low-confidence filename sequence blocks as an explicit ablation.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def make_groups(
    rows: list[dict[str, str]],
    manifest: dict[str, dict[str, str]],
    exact_duplicate_rows: list[dict[str, str]],
    near_pairs: list[dict[str, str]],
    mode: str,
    allow_provisional: bool,
) -> dict[str, str]:
    filenames = [row["filename"] for row in rows]
    if mode == "provisional_sequence":
        methods = {
            manifest[name].get("sequence_id_method", "")
            for name in filenames
        }
        if not allow_provisional:
            raise ValueError(
                "provisional_sequence is low confidence; pass --allow-provisional "
                "only for an ablation, not the final Group Fold."
            )
        return {name: manifest[name]["sequence_id"] for name in filenames}

    union_find = UnionFind(filenames)
    known = set(filenames)
    exact_members: dict[str, list[str]] = defaultdict(list)
    for row in exact_duplicate_rows:
        filename = row["filename"]
        if filename in known and row.get("duplicate_group"):
            exact_members[row["duplicate_group"]].append(filename)
    for members in exact_members.values():
        for filename in members[1:]:
            union_find.union(members[0], filename)
    for pair in near_pairs:
        left = pair["left_filename"]
        right = pair["right_filename"]
        if left in known and right in known:
            union_find.union(left, right)
    roots = {name: union_find.find(name) for name in filenames}
    root_numbers = {
        root: f"dup_near_{index:04d}"
        for index, root in enumerate(sorted(set(roots.values())))
    }
    return {name: root_numbers[root] for name, root in roots.items()}


def main() -> int:
    args = parse_args()
    if args.folds < 2:
        raise ValueError("--folds must be at least 2")
    generated_dir = args.generated_dir.resolve()
    train_rows = [
        row for row in read_csv(generated_dir / "train_index.csv")
        if row.get("training_use", "").lower() == "true"
    ]
    manifest_rows = read_csv(generated_dir / "data_manifest.csv")
    manifest = {row["filename"]: row for row in manifest_rows}
    exact_duplicate_rows = read_csv(generated_dir / "exact_duplicate_groups.csv")
    near_pairs = read_csv(generated_dir / "near_duplicate_candidates.csv")
    if not train_rows:
        raise ValueError("no enabled labeled training rows found")
    if any(row["filename"] not in manifest for row in train_rows):
        raise ValueError("train_index contains filenames missing from data_manifest")

    groups = make_groups(
        train_rows,
        manifest,
        exact_duplicate_rows,
        near_pairs,
        args.group_mode,
        args.allow_provisional,
    )
    if len(set(groups.values())) < args.folds:
        raise ValueError(
            f"only {len(set(groups.values()))} groups available for {args.folds} folds"
        )

    labels = np.asarray([row["label"] for row in train_rows])
    group_values = np.asarray([groups[row["filename"]] for row in train_rows])
    splitter = StratifiedGroupKFold(
        n_splits=args.folds, shuffle=True, random_state=args.seed
    )
    fold_by_filename: dict[str, int] = {}
    fold_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for fold, (_, validation_indices) in enumerate(
        splitter.split(np.zeros(len(train_rows)), labels, group_values)
    ):
        for index in validation_indices:
            filename = train_rows[index]["filename"]
            fold_by_filename[filename] = fold
            fold_counts[str(fold)][train_rows[index]["label"]] += 1

    if len(fold_by_filename) != len(train_rows):
        raise RuntimeError("some training rows did not receive a fold")

    output_rows = []
    for row in train_rows:
        output_rows.append(
            {
                "filename": row["filename"],
                "relative_path": row["relative_path"],
                "label": row["label"],
                "group_id": groups[row["filename"]],
                "group_mode": args.group_mode,
                "fold": fold_by_filename[row["filename"]],
            }
        )
    output_path = generated_dir / f"internal_cv_{args.group_mode}_{args.folds}fold.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("filename", "relative_path", "label", "group_id", "group_mode", "fold"),
        )
        writer.writeheader()
        writer.writerows(output_rows)

    report = {
        "folds": args.folds,
        "seed": args.seed,
        "group_mode": args.group_mode,
        "group_count": len(set(groups.values())),
        "row_count": len(train_rows),
        "fold_class_counts": {
            fold: dict(counts) for fold, counts in sorted(fold_counts.items())
        },
        "missing_labels_by_fold": {
            fold: [label for label in LABELS if counts[label] == 0]
            for fold, counts in sorted(fold_counts.items())
        },
        "final_group_fold_ready": False,
        "note": (
            "exact and near duplicate components are kept together; final Group Fold "
            "still requires confirmed visual/source sequence groups."
        ),
        "output": str(output_path),
    }
    (generated_dir / f"internal_cv_{args.group_mode}_{args.folds}fold.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
