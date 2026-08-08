"""Apply the manually confirmed camera-group merges to camera_group v1.

This is intentionally a small provenance-preserving repair: it does not
recluster images or change labels.  It only unions the explicitly reviewed
v1 groups and a few reviewed filename ranges, then emits a CV-ready manifest
that excludes the five disabled training images.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


class UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def frame_number(row: dict[str, str]) -> int:
    try:
        return int(row.get("frame_id", ""))
    except ValueError:
        return int(Path(row["filename"]).stem)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--active-train-index", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_rows = read_csv(args.base_manifest.resolve())
    review_rows = read_csv(args.review_csv.resolve())
    active_rows = read_csv(args.active_train_index.resolve())
    if not base_rows:
        raise ValueError("base manifest is empty")

    group_ids = sorted({row["camera_group"] for row in base_rows})
    uf = UnionFind(group_ids)
    merge_reasons: dict[str, list[str]] = defaultdict(list)
    filename_rows = {row["filename"]: row for row in base_rows}
    group_members: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in base_rows:
        group_members[row["camera_group"]].append(row)

    merge_records: list[dict[str, object]] = []

    def union_groups(groups: list[str], reason: str, source: str) -> None:
        groups = sorted({group for group in groups if group in uf.parent})
        if len(groups) < 2:
            return
        root = groups[0]
        for group in groups[1:]:
            uf.union(root, group)
        merge_records.append(
            {
                "source": source,
                "reason": reason,
                "original_groups": "|".join(groups),
                "filenames": "|".join(
                    sorted(
                        row["filename"]
                        for group in groups
                        for row in group_members[group]
                    )
                ),
            }
        )

    # The CSV is the minimum set of manually confirmed edges.  We apply both
    # critical train edges and high-confidence test-side under-group edges.
    for review in review_rows:
        group_a = review.get("group_a", "").strip()
        group_b = review.get("group_b", "").strip()
        if not group_a or not group_b:
            continue
        if review.get("severity") not in {"critical", "high"}:
            continue
        union_groups(
            [group_a, group_b],
            review.get("visual_judgement", "reviewed same camera/scene"),
            f"critical_findings.csv:{review.get('file_a','')}~{review.get('file_b','')}",
        )

    def groups_for_range(start: int, end: int, split: str) -> list[str]:
        return sorted(
            {
                row["camera_group"]
                for row in base_rows
                if row["split"] == split and start <= frame_number(row) <= end
            }
        )

    reviewed_ranges = [
        (759, 768, "train", "同一坝体/水尺固定监控系列，人工复核建议整体合并"),
        (2097, 2111, "train", "同一固定机位乱堆序列，人工复核明确应整体合并"),
        (2163, 2175, "test", "同一溪流固定机位测试序列，人工复核建议整体合并"),
        (2185, 2189, "test", "同一高点河道固定机位测试序列，人工复核建议整体合并"),
        (2212, 2214, "test", "同一桥侧/河道固定机位测试序列，人工复核建议整体合并"),
        (2295, 2296, "test", "同一固定机位测试序列，人工复核建议整体合并"),
        (2299, 2302, "test", "同一河道固定机位测试序列，人工复核建议整体合并"),
    ]
    for start, end, split, reason in reviewed_ranges:
        union_groups(groups_for_range(start, end, split), reason, f"CAMERA_GROUP_V1_REVIEW.md:{start}-{end}")

    components: dict[str, list[str]] = defaultdict(list)
    for group in group_ids:
        components[uf.find(group)].append(group)
    ordered_components = sorted(
        components.values(),
        key=lambda groups: min(frame_number(row) for group in groups for row in group_members[group]),
    )
    new_group_by_old: dict[str, str] = {}
    for number, groups in enumerate(ordered_components, start=1):
        new_id = f"camera_group_v2_{number:04d}"
        for group in groups:
            new_group_by_old[group] = new_id

    active_names = {row["filename"] for row in active_rows}
    base_names = set(filename_rows)
    missing = sorted(active_names - base_names)
    if missing:
        raise ValueError(f"active train index contains missing camera rows: {missing[:5]}")

    new_rows: list[dict[str, object]] = []
    for row in sorted(base_rows, key=lambda item: (frame_number(item), item["split"], item["filename"])):
        old_group = row["camera_group"]
        new_group = new_group_by_old[old_group]
        component = next(groups for groups in ordered_components if old_group in groups)
        component_filenames = sorted(
            filename
            for group in component
            for filename in (member["filename"] for member in group_members[group])
        )
        reasons = [
            record["reason"]
            for record in merge_records
            if any(group in component for group in record["original_groups"].split("|"))
        ]
        output = dict(row)
        output.update(
            {
                "camera_group_v1": old_group,
                "camera_group": new_group,
                "camera_group_size": len(component_filenames),
                "camera_group_v2_manual_merge": "yes" if len(component) > 1 else "no",
                "camera_group_v2_merge_reason": " || ".join(dict.fromkeys(reasons)),
                "enabled_for_cv": "yes" if row["split"] == "test" or row["filename"] in active_names else "no",
            }
        )
        new_rows.append(output)

    cv_rows = [row for row in new_rows if row["enabled_for_cv"] == "yes"]
    summary_rows: list[dict[str, object]] = []
    for group_id, members in sorted(
        ((group_id, [row for row in new_rows if row["camera_group"] == group_id]) for group_id in {row["camera_group"] for row in new_rows}),
        key=lambda item: min(int(row["frame_id"]) for row in item[1]),
    ):
        train_members = [row for row in members if row["split"] == "train"]
        test_members = [row for row in members if row["split"] == "test"]
        summary_rows.append(
            {
                "camera_group": group_id,
                "total_count": len(members),
                "train_count": len(train_members),
                "test_count": len(test_members),
                "active_train_count": sum(row["enabled_for_cv"] == "yes" for row in train_members),
                "frame_min": min(int(row["frame_id"]) for row in members),
                "frame_max": max(int(row["frame_id"]) for row in members),
                "members": "|".join(row["filename"] for row in members),
                "manual_merge": "yes" if any(row["camera_group_v2_manual_merge"] == "yes" for row in members) else "no",
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "camera_group_manifest_full.csv", new_rows)
    write_csv(args.out_dir / "camera_group_manifest_cv.csv", cv_rows)
    write_csv(args.out_dir / "camera_group_summary.csv", summary_rows)
    write_csv(args.out_dir / "camera_group_merges.csv", merge_records)

    manual_groups = [row for row in summary_rows if row["manual_merge"] == "yes"]
    report = [
        "# Camera Group v2 reviewed repair",
        "",
        "本版本只应用人工复核中明确的同机位/同场景合并，不重新推断标签，不修改原始 manifest 或 Fold。",
        "",
        f"- full rows: {len(new_rows)} (train={sum(row['split'] == 'train' for row in new_rows)}, test={sum(row['split'] == 'test' for row in new_rows)})",
        f"- CV rows: {len(cv_rows)} (active train={sum(row['split'] == 'train' for row in cv_rows)}, test={sum(row['split'] == 'test' for row in cv_rows)})",
        f"- v1 groups: {len(group_ids)}; v2 groups: {len(summary_rows)}",
        f"- repaired merged components: {len(manual_groups)}",
        "",
        "## Applied repair scope",
        "",
        "- critical cross-fold pairs from critical_findings.csv",
        "- train fixed-camera ranges 00759–00768 and 02097–02111",
        "- reviewed test fixed-camera ranges 02163–02175, 02185–02189, 02212–02214, 02295–02296, 02299–02302",
        "",
        "## Files",
        "",
        "- camera_group_manifest_full.csv: all source rows with v1/v2 provenance",
        "- camera_group_manifest_cv.csv: 1139 active train rows plus 695 test rows for GroupKFold construction",
        "- camera_group_merges.csv: applied reviewed merge records",
        "- camera_group_summary.csv: v2 group membership summary",
        "",
        "## Limits",
        "",
        "This is a reviewed repair pass, not a full SIFT/ORB reclustering. New group folds must be rebuilt from camera_group_manifest_cv.csv before using OOF as a model-selection metric.",
    ]
    (args.out_dir / "CAMERA_GROUP_V2_REPAIR.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (args.out_dir / "CAMERA_GROUP_V2_REPAIR.json").write_text(
        json.dumps(
            {
                "full_rows": len(new_rows),
                "cv_rows": len(cv_rows),
                "active_train_rows": sum(row["split"] == "train" for row in cv_rows),
                "test_rows": sum(row["split"] == "test" for row in cv_rows),
                "v1_groups": len(group_ids),
                "v2_groups": len(summary_rows),
                "manual_merged_components": len(manual_groups),
                "source": str(args.base_manifest.resolve()),
                "review": str(args.review_csv.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"full_rows": len(new_rows), "cv_rows": len(cv_rows), "v1_groups": len(group_ids), "v2_groups": len(summary_rows), "merged_components": len(manual_groups)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
