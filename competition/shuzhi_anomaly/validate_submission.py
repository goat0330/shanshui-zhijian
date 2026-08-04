"""Validate a competition-3 single-label submission against the frozen manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parent / "generated" / "test_manifest_v1.csv",
    )
    args = parser.parse_args()
    manifest = read_csv(args.manifest.resolve())
    result = json.loads(args.submission.resolve().read_text(encoding="utf-8"))
    if not isinstance(result, list):
        raise ValueError("submission must be a JSON list")
    expected = [row["filename"] for row in manifest]
    actual = [str(row.get("filename", "")) for row in result]
    if actual != expected:
        raise ValueError("filename order or coverage does not match test_manifest_v1.csv")
    for expected_row, row in zip(manifest, result):
        if not isinstance(row, dict):
            raise ValueError("each submission item must be a JSON object")
        if not all(isinstance(row.get(field), str) for field in ("filename", "width", "height", "label")):
            raise ValueError(f"filename, width, height, and label must all be JSON strings for {row.get('filename')}")
        if row.get("label") not in LABELS:
            raise ValueError(f"invalid label for {row.get('filename')}: {row.get('label')}")
        if str(row.get("width")) != str(expected_row["width"]) or str(row.get("height")) != str(expected_row["height"]):
            raise ValueError(f"dimension mismatch for {row.get('filename')}")
        if set(row) != {"filename", "width", "height", "label"}:
            raise ValueError(f"unexpected fields for {row.get('filename')}: {sorted(row)}")
    print(json.dumps({"valid": True, "count": len(result), "labels": sorted({row["label"] for row in result})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
