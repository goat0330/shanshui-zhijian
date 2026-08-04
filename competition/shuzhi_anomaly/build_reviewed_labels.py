"""Create an official-label passthrough version without changing train.json."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path,
                        default=Path(r"D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集"))
    parser.add_argument("--generated-dir", type=Path, default=Path("competition/shuzhi_anomaly/generated"))
    parser.add_argument("--label-map", type=Path, default=Path("competition/shuzhi_anomaly/config/label_map.json"))
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    generated = args.generated_dir.resolve()
    train_json = source_root / "train.json"
    records = json.loads(train_json.read_text(encoding="utf-8"))
    label_map = json.loads(args.label_map.resolve().read_text(encoding="utf-8"))
    if tuple(label_map) != LABELS or set(label_map) != set(LABELS):
        raise ValueError("label_map.json does not match the official six-label order")
    if any(record.get("label") not in LABELS for record in records):
        raise ValueError("train.json contains a label outside the official six labels")

    candidates = read_csv(generated / "label_review_candidates.csv")
    decisions = []
    for row in candidates:
        decisions.append({
            "filename": row["filename"],
            "relative_path": row["relative_path"],
            "original_label": row["original_label"],
            "reviewed_label": row["original_label"],
            "alternate_label": "",
            "decision_type": "official_label_passthrough",
            "manual_visual_review": "false",
            "confidence": "official_label_in_train_json",
            "review_status": "official_label_retained_pending_visual_review",
            "review_notes": "P0不擅自改写官方train.json标签；视觉复核未完成。",
            "evidence_scale": row.get("evidence_scale", ""),
            "evidence_location": row.get("evidence_location", ""),
        })
    decision_path = generated / "review_decisions.csv"
    with decision_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = tuple(decisions[0]) if decisions else (
            "filename", "relative_path", "original_label", "reviewed_label", "alternate_label",
            "decision_type", "manual_visual_review", "confidence", "review_status",
            "review_notes", "evidence_scale", "evidence_location",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(decisions)

    reviewed_path = generated / "train_reviewed_v1.json"
    reviewed_path.write_text(json.dumps(records, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    audit = {
        "dataset_version": "reviewed_v1",
        "source_train_json": str(train_json),
        "source_train_json_sha256": sha256(train_json),
        "record_count": len(records),
        "decision_count": len(decisions),
        "changed_label_count": 0,
        "manual_visual_review_count": 0,
        "policy": "Official labels are retained; no semantic relabeling is performed in P0.",
        "review_decisions": str(decision_path),
        "train_reviewed": str(reviewed_path),
    }
    (generated / "reviewed_label_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
