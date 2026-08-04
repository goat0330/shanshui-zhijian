"""Export a six-label submission from the frozen test manifest."""

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
    parser.add_argument("--manifest", type=Path, default=Path("competition/shuzhi_anomaly/generated/test_manifest_v1.csv"))
    parser.add_argument("--label", choices=LABELS, default="有漂浮物")
    parser.add_argument("--output", type=Path, default=Path("competition/shuzhi_anomaly/generated/submission_b0.json"))
    args = parser.parse_args()
    rows = read_csv(args.manifest.resolve())
    result = [
        {
            "filename": row["filename"],
            "width": str(row["width"]),
            "height": str(row["height"]),
            "label": args.label,
        }
        for row in rows
    ]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "count": len(result), "label": args.label}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
