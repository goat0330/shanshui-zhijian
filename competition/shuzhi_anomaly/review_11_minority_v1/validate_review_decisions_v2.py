"""Strictly validate a completed 11-image review CSV.

Unlike the original validator, this rejects unfinished blank review fields and
checks consistency between review_status and reviewed_label.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

LABELS = {"乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常"}
STATUSES = {"confirmed", "relabel", "uncertain", "exclude_from_strict_validation"}
CONFIDENCES = {"high", "medium", "low"}
EVIDENCE = {"local", "global", "none"}
FLOATING = {"yes", "no", "unclear"}
EXPECTED = {
    "02486.jpg", "02487.jpg", "02488.jpg", "02489.jpg",
    "00033.jpg", "00064.jpg", "00096.jpg", "00100.jpg",
    "00114.jpg", "01086.jpg", "02111.jpg",
}
REQUIRED = {
    "filename", "official_label", "model_pred", "reviewed_label",
    "review_status", "confidence", "evidence_scale",
    "has_floating_object", "same_scene_group", "review_notes",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    with args.csv_path.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("CSV is empty")
    missing = REQUIRED - set(rows[0])
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")

    names = [row.get("filename", "").strip() for row in rows]
    if set(names) != EXPECTED or len(names) != len(EXPECTED):
        raise ValueError("CSV must contain exactly the 11 packaged filenames once")

    for row in rows:
        name = row["filename"].strip()
        official = row["official_label"].strip()
        pred = row["model_pred"].strip()
        reviewed = row["reviewed_label"].strip()
        status = row["review_status"].strip()
        confidence = row["confidence"].strip()
        evidence = row["evidence_scale"].strip()
        floating = row["has_floating_object"].strip()
        notes = row["review_notes"].strip()

        if official not in LABELS or pred not in LABELS or reviewed not in LABELS:
            raise ValueError(f"invalid label value: {name}")
        if status not in STATUSES:
            raise ValueError(f"invalid review_status: {name}")
        if confidence not in CONFIDENCES:
            raise ValueError(f"invalid confidence: {name}")
        if evidence not in EVIDENCE:
            raise ValueError(f"invalid evidence_scale: {name}")
        if floating not in FLOATING:
            raise ValueError(f"invalid has_floating_object: {name}")
        if not notes:
            raise ValueError(f"review_notes must not be blank: {name}")

        if status == "confirmed" and reviewed != official:
            raise ValueError(f"confirmed sample must retain official label: {name}")
        if status == "relabel" and reviewed == official:
            raise ValueError(f"relabel sample must change the official label: {name}")
        if status == "uncertain" and reviewed != official:
            raise ValueError(f"uncertain sample must retain official label: {name}")

    relabels = sum(row["review_status"].strip() == "relabel" for row in rows)
    print(f"strictly valid completed review CSV: {len(rows)} rows; relabels={relabels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
