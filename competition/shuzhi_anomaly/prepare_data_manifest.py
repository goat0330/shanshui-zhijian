"""Build a low-token audit manifest for the six-class water anomaly data.

This script does not inspect image semantics. It only checks file/label
integrity, decodability, dimensions, exact duplicates, and a provisional
filename-based sequence block. The sequence block is explicitly provisional
because the released data has no source video metadata.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
CSV_FIELDS = (
    "filename",
    "relative_path",
    "split",
    "label",
    "frame_id",
    "sequence_id",
    "sequence_id_method",
    "width",
    "height",
    "declared_width",
    "declared_height",
    "sha256",
    "difference_hash",
    "image_ok",
    "size_mismatch",
    "duplicate_group",
    "training_use",
    "training_exclusion_reason",
    "review_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(r"D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集"),
    )
    parser.add_argument("--labels-json", type=Path, default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("competition/shuzhi_anomaly/generated"),
    )
    parser.add_argument(
        "--sequence-gap",
        type=int,
        default=1,
        help="Start a new provisional block when numeric filenames differ by more than this.",
    )
    parser.add_argument(
        "--near-hash-threshold",
        type=int,
        default=2,
        help="Maximum dHash Hamming distance for review candidates; does not delete files.",
    )
    parser.add_argument(
        "--near-frame-gap",
        type=int,
        default=2,
        help="Only compare provisional neighboring frames within this numeric gap.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def difference_hash(path: Path) -> str:
    """Return a small CPU-only perceptual hash for review candidates."""
    with Image.open(path) as opened:
        gray = opened.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
    pixels = list(gray.getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | int(pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return f"{value:016x}"


def difference_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def filename_number(filename: str) -> int | None:
    stem = Path(filename).stem
    return int(stem) if stem.isdigit() else None


def infer_split(path: Path) -> str:
    parts = set(path.parts)
    if "训练集" in parts:
        return "train"
    if "验证集" in parts:
        return "val"
    if "初赛测试集" in parts or "测试集" in parts:
        return "test"
    return "unknown"


def load_labels(path: Path) -> dict[str, dict[str, object]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"labels JSON must be a list: {path}")
    labels: dict[str, dict[str, object]] = {}
    for record in records:
        filename = str(record["filename"])
        if filename in labels:
            raise ValueError(f"duplicate filename in labels JSON: {filename}")
        label = str(record["label"])
        if label not in LABELS:
            raise ValueError(f"unexpected label {label!r} for {filename}")
        labels[filename] = {
            "label": label,
            "width": int(record["width"]),
            "height": int(record["height"]),
        }
    return labels


def provisional_sequences(rows: list[dict[str, object]], gap: int) -> None:
    numbered = sorted(
        (row for row in rows if row["frame_id"] != ""),
        key=lambda row: int(row["frame_id"]),
    )
    block = -1
    previous: int | None = None
    for row in numbered:
        current = int(row["frame_id"])
        if previous is None or current - previous > gap:
            block += 1
        row["sequence_id"] = f"file_block_{block:04d}"
        previous = current
    for row in rows:
        if row["frame_id"] == "":
            row["sequence_id"] = "file_block_unknown"


def write_csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def duplicate_group_type(members: list[dict[str, object]]) -> str:
    splits = {str(row["split"]) for row in members}
    if splits == {"train"}:
        return "train_train"
    if splits == {"test"}:
        return "test_test"
    if "train" in splits and "test" in splits:
        return "train_test"
    return "other_split"


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    labels_path = (args.labels_json or source_root / "train.json").resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    labels = load_labels(labels_path)
    images = sorted(
        (
            image
            for image in source_root.rglob("*")
            if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda image: image.relative_to(source_root).as_posix(),
    )
    by_name: dict[str, list[Path]] = defaultdict(list)
    for image in images:
        by_name[image.name].append(image)

    rows: list[dict[str, object]] = []
    for image in images:
        filename = image.name
        annotation = labels.get(filename, {})
        frame_id = filename_number(filename)
        row: dict[str, object] = {
            "filename": filename,
            "relative_path": image.relative_to(source_root).as_posix(),
            "split": infer_split(image.relative_to(source_root)),
            "label": annotation.get("label", ""),
            "frame_id": "" if frame_id is None else frame_id,
            "sequence_id": "",
            "sequence_id_method": "filename_contiguous_block_provisional",
            "width": "",
            "height": "",
            "declared_width": annotation.get("width", ""),
            "declared_height": annotation.get("height", ""),
            "sha256": "",
            "difference_hash": "",
            "image_ok": False,
            "size_mismatch": False,
            "duplicate_group": "",
            "training_use": "",
            "training_exclusion_reason": "",
            "review_status": "unlabeled" if filename not in labels else "unreviewed",
        }
        try:
            with Image.open(image) as opened:
                opened.verify()
            with Image.open(image) as opened:
                width, height = opened.size
            row["width"] = width
            row["height"] = height
            row["image_ok"] = True
            row["size_mismatch"] = (
                bool(annotation)
                and (width != annotation["width"] or height != annotation["height"])
            )
            row["sha256"] = sha256(image)
            row["difference_hash"] = difference_hash(image)
        except Exception as exc:  # report the row instead of hiding a bad file
            row["review_status"] = f"decode_error:{type(exc).__name__}"
        rows.append(row)

    provisional_sequences(rows, args.sequence_gap)

    by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["sha256"]:
            by_hash[str(row["sha256"])].append(row)
    duplicate_groups: list[list[dict[str, object]]] = []
    for members in by_hash.values():
        if len(members) > 1:
            group_id = f"dup_{len(duplicate_groups):04d}"
            for row in members:
                row["duplicate_group"] = group_id
            duplicate_groups.append(members)

    # Non-destructive training index: only later exact duplicates in the
    # labeled training split are disabled. Source images are never deleted.
    train_rows = sorted(
        (row for row in rows if row["split"] == "train" and row["label"]),
        key=lambda row: (
            int(row["frame_id"]) if row["frame_id"] != "" else 10**12,
            str(row["relative_path"]),
        ),
    )
    for row in train_rows:
        row["training_use"] = True
    train_hash_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in train_rows:
        if row["sha256"]:
            train_hash_groups[str(row["sha256"])].append(row)
    for members in train_hash_groups.values():
        for duplicate in members[1:]:
            duplicate["training_use"] = False
            duplicate["training_exclusion_reason"] = "exact_duplicate_later"

    # Near duplicates are review candidates only. dHash similarity is not
    # proof of the same scene, so no near-duplicate image is auto-excluded.
    hash_rows = [row for row in rows if row["image_ok"] and row["difference_hash"]]
    near_pairs: list[dict[str, object]] = []
    near_candidate_names: set[str] = set()
    for index, left in enumerate(hash_rows):
        for right in hash_rows[index + 1 :]:
            if left["frame_id"] == "" or right["frame_id"] == "":
                continue
            if int(right["frame_id"]) - int(left["frame_id"]) > args.near_frame_gap:
                break
            if left["sha256"] == right["sha256"]:
                continue
            distance = difference_distance(
                str(left["difference_hash"]), str(right["difference_hash"])
            )
            if distance <= args.near_hash_threshold:
                near_pairs.append(
                    {
                        "left_filename": left["filename"],
                        "right_filename": right["filename"],
                        "left_path": left["relative_path"],
                        "right_path": right["relative_path"],
                        "left_split": left["split"],
                        "right_split": right["split"],
                        "left_label": left["label"],
                        "right_label": right["label"],
                        "hamming_distance": distance,
                    }
                )
                near_candidate_names.update(
                    (str(left["filename"]), str(right["filename"]))
                )

    near_parent: dict[str, str] = {}

    def near_find(value: str) -> str:
        near_parent.setdefault(value, value)
        if near_parent[value] != value:
            near_parent[value] = near_find(near_parent[value])
        return near_parent[value]

    def near_union(left: str, right: str) -> None:
        left_root = near_find(left)
        right_root = near_find(right)
        if left_root != right_root:
            near_parent[right_root] = left_root

    for pair in near_pairs:
        near_union(str(pair["left_filename"]), str(pair["right_filename"]))
    near_roots = {name: near_find(name) for name in near_parent}
    near_group_ids = {
        root: f"near_{index:04d}"
        for index, root in enumerate(sorted(set(near_roots.values())))
    }
    near_group_by_name = {
        name: near_group_ids[root] for name, root in near_roots.items()
    }

    review_reasons: dict[str, set[str]] = defaultdict(set)
    label_counts = Counter(str(row["label"]) for row in train_rows)
    minority_threshold = 60
    for row in train_rows:
        filename = str(row["filename"])
        if label_counts[str(row["label"])] <= minority_threshold:
            review_reasons[filename].add("minority_class")
        if row["size_mismatch"]:
            review_reasons[filename].add("size_mismatch")
        if row["duplicate_group"]:
            review_reasons[filename].add("exact_duplicate")
        if filename in near_candidate_names:
            review_reasons[filename].add("near_duplicate_candidate")
    review_rows = []
    for row in train_rows:
        reasons = sorted(review_reasons.get(str(row["filename"]), set()))
        if reasons:
            minority = label_counts[str(row["label"])] <= minority_threshold
            priority = 1 if minority else 2
            review_rows.append(
                {
                    "filename": row["filename"],
                    "relative_path": row["relative_path"],
                    "original_label": row["label"],
                    "reviewed_label": "",
                    "alternate_label": "",
                    "sequence_id": row["sequence_id"],
                    "scene_id": row["sequence_id"],
                    "source_type": "filename_contiguous_block_provisional",
                    "confidence": "low",
                    "reasons": ";".join(reasons),
                    "priority": priority,
                    "review_status": "pending_manual_review",
                    "evidence_scale": "",
                    "evidence_location": "",
                    "review_notes": "",
                }
            )
    review_rows.sort(
        key=lambda row: (
            int(row["priority"]),
            str(row["original_label"]),
            str(row["filename"]),
        )
    )

    sequence_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        sequence_rows[str(row["sequence_id"])].append(row)
    sequence_summary = []
    for sequence_id, members in sorted(sequence_rows.items()):
        sequence_summary.append(
            {
                "sequence_id": sequence_id,
                "sequence_id_method": "filename_contiguous_block_provisional",
                "confidence": "low",
                "total_count": len(members),
                "train_count": sum(row["split"] == "train" for row in members),
                "val_count": sum(row["split"] == "val" for row in members),
                "test_count": sum(row["split"] == "test" for row in members),
                "labels": ";".join(
                    f"{label}:{count}"
                    for label, count in sorted(
                        Counter(
                            str(row["label"])
                            for row in members
                            if row["label"]
                        ).items()
                    )
                ),
                "review_status": "needs_source_video_or_manual_review",
            }
        )

    write_csv(out_dir / "data_manifest.csv", rows, CSV_FIELDS)
    duplicate_rows = []
    duplicate_group_types: Counter[str] = Counter()
    exact_duplicate_overrides: list[dict[str, object]] = []
    for members in duplicate_groups:
        group_type = duplicate_group_type(members)
        duplicate_group_types[group_type] += 1
        if group_type == "train_test":
            exact_duplicate_overrides.append(
                {
                    "duplicate_group": members[0]["duplicate_group"],
                    "sha256": members[0]["sha256"],
                    "members": [
                        {
                            "filename": row["filename"],
                            "relative_path": row["relative_path"],
                            "split": row["split"],
                            "label": row["label"],
                        }
                        for row in members
                    ],
                    "decision": "pending_competition_rule",
                }
            )
        for row in members:
            duplicate_rows.append(
                {
                    "duplicate_group": row["duplicate_group"],
                    "duplicate_group_type": group_type,
                    "sha256": row["sha256"],
                    "filename": row["filename"],
                    "relative_path": row["relative_path"],
                    "split": row["split"],
                    "label": row["label"],
                }
            )
    write_csv(
        out_dir / "exact_duplicate_groups.csv",
        duplicate_rows,
        (
            "duplicate_group", "duplicate_group_type", "sha256", "filename",
            "relative_path", "split", "label",
        ),
    )
    (out_dir / "exact_duplicate_override.json").write_text(
        json.dumps(exact_duplicate_overrides, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(
        out_dir / "near_duplicate_candidates.csv",
        near_pairs,
        (
            "left_filename", "right_filename", "left_path", "right_path",
            "left_split", "right_split", "left_label", "right_label", "hamming_distance",
        ),
    )
    write_csv(
        out_dir / "train_index.csv",
        train_rows,
        (
            "filename", "relative_path", "label", "frame_id", "sequence_id",
            "sha256", "difference_hash", "training_use", "training_exclusion_reason",
        ),
    )
    write_csv(
        out_dir / "label_review_candidates.csv",
        review_rows,
        (
            "filename", "relative_path", "original_label", "reviewed_label",
            "alternate_label", "sequence_id", "scene_id", "source_type",
            "confidence", "reasons", "priority", "review_status", "review_notes",
            "evidence_scale", "evidence_location",
        ),
    )
    train_manifest_rows = []
    for row in train_rows:
        train_manifest_rows.append(
            {
                "filename": row["filename"],
                "relative_path": row["relative_path"],
                "label": row["label"],
                "width": row["width"],
                "height": row["height"],
                "sha256": row["sha256"],
                "difference_hash": row["difference_hash"],
                "decode_status": "ok" if row["image_ok"] else row["review_status"],
                "enabled": row["training_use"],
                "duplicate_group_id": row["duplicate_group"],
                "near_duplicate_group_id": near_group_by_name.get(str(row["filename"]), ""),
                "scene_id": row["sequence_id"],
            }
        )
    train_manifest_path = out_dir / "train_manifest_v1.csv"
    write_csv(
        train_manifest_path,
        train_manifest_rows,
        (
            "filename", "relative_path", "label", "width", "height", "sha256",
            "difference_hash", "decode_status", "enabled", "duplicate_group_id",
            "near_duplicate_group_id", "scene_id",
        ),
    )
    (out_dir / "train_manifest_v1.sha256").write_text(
        sha256(train_manifest_path) + "  train_manifest_v1.csv\n", encoding="utf-8"
    )
    test_rows = sorted(
        (row for row in rows if row["split"] == "test"),
        key=lambda row: (
            int(row["frame_id"]) if row["frame_id"] != "" else 10**12,
            str(row["relative_path"]),
        ),
    )
    test_manifest_rows = []
    for order, row in enumerate(test_rows, start=1):
        test_manifest_rows.append(
            {
                "submission_order": order,
                "filename": row["filename"],
                "relative_path": row["relative_path"],
                "width": row["width"],
                "height": row["height"],
                "sha256": row["sha256"],
                "image_ok": row["image_ok"],
            }
        )
    test_manifest_path = out_dir / "test_manifest_v1.csv"
    write_csv(
        test_manifest_path,
        test_manifest_rows,
        ("submission_order", "filename", "relative_path", "width", "height", "sha256", "image_ok"),
    )
    (out_dir / "test_manifest_v1.sha256").write_text(
        sha256(test_manifest_path) + "  test_manifest_v1.csv\n", encoding="utf-8"
    )
    test_diff_rows = []
    for row in test_rows:
        extension = Path(str(row["filename"])).suffix.lower()
        if extension != ".jpg":
            test_diff_rows.append(
                {
                    "filename": row["filename"],
                    "relative_path": row["relative_path"],
                    "extension": extension,
                    "jpg_only_scan": False,
                    "all_supported_image_scan": True,
                    "reason": "supported_non_jpg_image_omitted_by_691_scan",
                    "decision": "include_in_test_manifest_v1",
                }
            )
    write_csv(
        out_dir / "test_691_vs_695_diff.csv",
        test_diff_rows,
        (
            "filename", "relative_path", "extension", "jpg_only_scan",
            "all_supported_image_scan", "reason", "decision",
        ),
    )
    write_csv(
        out_dir / "sequence_review_summary.csv",
        sequence_summary,
        (
            "sequence_id", "sequence_id_method", "confidence", "total_count",
            "train_count", "val_count", "test_count", "labels", "review_status",
        ),
    )

    labeled_names = set(labels)
    image_names = set(by_name)
    report = {
        "source_root": str(source_root),
        "labels_json": str(labels_path),
        "image_count": len(rows),
        "labeled_image_count": sum(bool(row["label"]) for row in rows),
        "label_count_in_json": len(labels),
        "missing_images_for_labels": sorted(labeled_names - image_names),
        "unlabeled_image_count": len(image_names - labeled_names),
        "unlabeled_image_preview": sorted(image_names - labeled_names)[:20],
        "split_counts": dict(Counter(str(row["split"]) for row in rows)),
        "label_counts": dict(Counter(str(row["label"]) for row in rows if row["label"])),
        "decode_error_count": sum(not row["image_ok"] for row in rows),
        "size_mismatch_count": sum(bool(row["size_mismatch"]) for row in rows),
        "exact_duplicate_group_count": len(duplicate_groups),
        "exact_duplicate_row_count": sum(len(group) for group in duplicate_groups),
        "cross_split_duplicate_groups": sum(
            len({str(row["split"]) for row in group}) > 1 for group in duplicate_groups
        ),
        "exact_duplicate_group_types": dict(duplicate_group_types),
        "exact_duplicate_override_count": len(exact_duplicate_overrides),
        "near_duplicate_candidate_pair_count": len(near_pairs),
        "near_duplicate_group_count": len(near_group_ids),
        "train_rows": len(train_rows),
        "train_rows_enabled": sum(row["training_use"] is True for row in train_rows),
        "label_review_candidate_count": len(review_rows),
        "validation_ready": any(row["split"] == "val" and row["label"] for row in rows),
        "provisional_sequence_count": len({row["sequence_id"] for row in rows}),
        "sequence_id_method": "filename contiguous blocks only; low-confidence review field, not final Group Fold",
        "supported_image_extensions": sorted(IMAGE_EXTENSIONS),
        "test_jpg_count": sum(Path(str(row["filename"])).suffix.lower() == ".jpg" for row in test_rows),
        "test_supported_image_count": len(test_rows),
        "test_non_jpg_count": len(test_diff_rows),
    }
    (out_dir / "audit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"unlabeled_image_preview", "missing_images_for_labels"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"manifest: {out_dir / 'data_manifest.csv'}")
    print(f"duplicates: {out_dir / 'exact_duplicate_groups.csv'}")
    print(f"near duplicates: {out_dir / 'near_duplicate_candidates.csv'}")
    print(f"train index: {out_dir / 'train_index.csv'}")
    print(f"train manifest: {train_manifest_path}")
    print(f"review queue: {out_dir / 'label_review_candidates.csv'}")
    print(f"test manifest: {test_manifest_path}")
    print(f"test 691 vs 695 diff: {out_dir / 'test_691_vs_695_diff.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
