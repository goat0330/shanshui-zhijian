"""Apply only confirmed v2 review decisions to a derived label file."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LABELS = {"乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(r"D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集"))
    parser.add_argument("--decisions", type=Path, default=Path("review_11_minority_v1/review_decisions_v2.csv"))
    parser.add_argument("--output", type=Path, default=Path("generated/train_reviewed_v2.json"))
    parser.add_argument("--audit", type=Path, default=Path("generated/reviewed_label_audit_v2.json"))
    args = parser.parse_args()

    train_path = args.source_root.resolve() / "train.json"
    records = json.loads(train_path.read_text(encoding="utf-8"))
    by_name = {str(row["filename"]): row for row in records}
    with args.decisions.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        decisions = list(csv.DictReader(handle))

    if len({row["filename"] for row in decisions}) != len(decisions):
        raise ValueError("review decisions contain duplicate filenames")
    overrides: dict[str, str] = {}
    for decision in decisions:
        name = decision["filename"]
        if name not in by_name:
            raise ValueError(f"review decision is not in train.json: {name}")
        official = decision["official_label"]
        source_label = by_name[name]["label"]
        reviewed = decision["reviewed_label"]
        if official != source_label:
            raise ValueError(f"official label mismatch for {name}: {official} vs {source_label}")
        if reviewed not in LABELS:
            raise ValueError(f"invalid reviewed label for {name}")
        overrides[name] = reviewed

    output_records = []
    changed = []
    for original in records:
        row = dict(original)
        name = str(row["filename"])
        if name in overrides and row["label"] != overrides[name]:
            changed.append({"filename": name, "from": row["label"], "to": overrides[name]})
            row["label"] = overrides[name]
        output_records.append(row)

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_records, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    audit = {
        "dataset_version": "reviewed_v2",
        "source_train_json": str(train_path),
        "source_train_json_sha256": sha256(train_path),
        "decision_csv": str(args.decisions.resolve()),
        "decision_csv_sha256": sha256(args.decisions.resolve()),
        "record_count": len(output_records),
        "decision_count": len(decisions),
        "changed_label_count": len(changed),
        "changed_labels": changed,
        "unreviewed_records_retain_official_labels": True,
        "raw_train_json_unchanged": True,
        "reviewed_output": str(output),
    }
    audit_path = args.audit.resolve()
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
