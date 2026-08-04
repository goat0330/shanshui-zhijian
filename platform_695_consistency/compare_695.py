from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")
FIELDS = ("filename", "width", "height", "label")


def load(path: Path) -> list[dict[str, str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"not a JSON list: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    platform = load(args.platform)
    reference = load(args.reference)
    differences: list[dict[str, str]] = []
    order_diff = 0
    for index in range(max(len(platform), len(reference))):
        left = platform[index] if index < len(platform) else {}
        right = reference[index] if index < len(reference) else {}
        changed = [field for field in FIELDS if str(left.get(field, "")) != str(right.get(field, ""))]
        if changed:
            differences.append({
                "index": str(index + 1),
                "filename": str(left.get("filename", right.get("filename", ""))),
                "platform_filename": str(left.get("filename", "")),
                "reference_filename": str(right.get("filename", "")),
                "platform_width": str(left.get("width", "")),
                "reference_width": str(right.get("width", "")),
                "platform_height": str(left.get("height", "")),
                "reference_height": str(right.get("height", "")),
                "platform_label": str(left.get("label", "")),
                "reference_label": str(right.get("label", "")),
                "difference_types": ";".join(changed),
            })
            if "filename" in changed:
                order_diff += 1
    args.diff.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "index", "filename", "platform_filename", "reference_filename",
        "platform_width", "reference_width", "platform_height", "reference_height",
        "platform_label", "reference_label", "difference_types",
    ]
    with args.diff.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(differences)
    label_diff = sum("label" in row["difference_types"].split(";") for row in differences)
    width_diff = sum("width" in row["difference_types"].split(";") for row in differences)
    height_diff = sum("height" in row["difference_types"].split(";") for row in differences)
    platform_labels = Counter(row.get("label") for row in platform)
    reference_labels = Counter(row.get("label") for row in reference)
    report = {
        "platform_count": len(platform),
        "reference_count": len(reference),
        "count_match": len(platform) == len(reference) == 695,
        "order_match": order_diff == 0 and [row.get("filename") for row in platform] == [row.get("filename") for row in reference],
        "filename_diff": order_diff,
        "width_diff": width_diff,
        "height_diff": height_diff,
        "label_diff": label_diff,
        "total_record_diff": len(differences),
        "platform_label_distribution": dict(platform_labels),
        "reference_label_distribution": dict(reference_labels),
        "status": "pass" if len(platform) == len(reference) == 695 and not differences else "fail",
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
