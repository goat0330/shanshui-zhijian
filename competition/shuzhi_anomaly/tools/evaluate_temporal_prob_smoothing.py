"""CPU screen for camera-group temporal probability smoothing.

Train evaluation uses an earlier-support/later-query split inside each camera
group. Test analysis is unlabeled and only reports how many predictions would
change; it is not treated as validation.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


LABELS = ["乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常"]
LABEL_TO_ID = {x: i for i, x in enumerate(LABELS)}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def order_key(row: dict[str, str]) -> tuple[int, str]:
    try:
        return int(float(row.get("frame_id", ""))), row["filename"]
    except ValueError:
        digits = "".join(c for c in row["filename"] if c.isdigit())
        return (int(digits) if digits else 10**12), row["filename"]


def prob_vector(row: dict[str, str], prefix: str = "prob_") -> np.ndarray:
    return np.array([float(row[f"{prefix}{label}"]) for label in LABELS], dtype=np.float64)


def score(y_true: list[int], y_pred: list[int]) -> tuple[float, float, float]:
    cm = np.zeros((len(LABELS), len(LABELS)), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    supports = cm.sum(axis=1)
    f1s, ious = [], []
    for i in range(len(LABELS)):
        tp = float(cm[i, i])
        fp = float(cm[:, i].sum() - tp)
        fn = float(cm[i, :].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall)
                   if precision + recall else 0.0)
        union = tp + fp + fn
        ious.append(tp / union if union else 0.0)
    n = len(y_true)
    wf1 = float(sum(f * s for f, s in zip(f1s, supports)) / n) if n else 0.0
    miou = float(np.mean([x for x, s in zip(ious, supports) if s > 0])) if n else 0.0
    acc = float(np.trace(cm) / n) if n else 0.0
    return acc, wf1, miou


def split_support(group_rows: list[dict[str, str]], fraction: float = 0.6):
    ordered = sorted(group_rows, key=order_key)
    n = len(ordered)
    if n < 4:
        return [], ordered
    support_n = max(2, min(int(round(n * fraction)), n - 2))
    return ordered[:support_n], ordered[support_n:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera-manifest", required=True)
    ap.add_argument("--train-oof", required=True)
    ap.add_argument("--test-probs", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    manifest = rows(Path(args.camera_manifest))
    train_oof = {r["filename"]: r for r in rows(Path(args.train_oof))}
    test_probs = {r["filename"]: r for r in rows(Path(args.test_probs))}
    train_groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    test_groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for r in manifest:
        if r.get("camera_group") == "":
            continue
        if r.get("split") == "train" and r.get("enabled_for_cv", "yes").lower() == "yes" and r["filename"] in train_oof:
            train_groups[r["camera_group"]].append(r)
        elif r.get("split") == "test" and r["filename"] in test_probs:
            test_groups[r["camera_group"]].append(r)

    betas = [0.0, 0.1, 0.2, 0.3, 0.5]
    y_true: list[int] = []
    query_base: list[np.ndarray] = []
    support_context: list[np.ndarray] = []
    for group in sorted(train_groups):
        support, query = split_support(train_groups[group])
        if not support:
            continue
        support_prob = np.median(np.stack([prob_vector(train_oof[r["filename"]]) for r in support]), axis=0)
        for r in query:
            y_true.append(LABEL_TO_ID[r["label"]])
            query_base.append(prob_vector(train_oof[r["filename"]]))
            support_context.append(support_prob)

    metric_rows = []
    for beta in betas:
        preds = [int(np.argmax((1 - beta) * p + beta * s))
                 for p, s in zip(query_base, support_context)]
        acc, wf1, miou = score(y_true, preds)
        metric_rows.append({
            "beta": beta,
            "query_n": len(y_true),
            "accuracy": acc,
            "weighted_f1": wf1,
            "miou": miou,
            "changed_from_base": sum(
                int(np.argmax(p)) != pred for p, pred in zip(query_base, preds)
            ),
        })

    # Test-side report only. Use same-group train OOF support where available;
    # otherwise use other unlabeled test frames in the same group.
    test_records = []
    for group, group_rows in sorted(test_groups.items()):
        train_support, _ = split_support(train_groups.get(group, []))
        if train_support:
            context = np.median(np.stack([prob_vector(train_oof[r["filename"]]) for r in train_support]), axis=0)
            context_source = "train_support"
        elif len(group_rows) >= 3:
            context = np.median(np.stack([prob_vector(test_probs[r["filename"]]) for r in group_rows]), axis=0)
            context_source = "unlabeled_test_group"
        else:
            continue
        for r in sorted(group_rows, key=order_key):
            base = prob_vector(test_probs[r["filename"]])
            item = {
                "filename": r["filename"],
                "camera_group": group,
                "context_source": context_source,
                "base_pred": LABELS[int(np.argmax(base))],
            }
            for beta in betas:
                pred = int(np.argmax((1 - beta) * base + beta * context))
                item[f"beta_{str(beta).replace('.', 'p')}"] = LABELS[pred]
            test_records.append(item)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    metric_path = out / "temporal_smoothing_metrics.csv"
    with metric_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metric_rows)
    test_path = out / "test_temporal_smoothing_changes.csv"
    if test_records:
        with test_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(test_records[0].keys()))
            writer.writeheader()
            writer.writerows(test_records)
    else:
        test_path.write_text("filename\n", encoding="utf-8-sig")

    baseline = metric_rows[0]
    best = max(metric_rows, key=lambda x: float(x["weighted_f1"]))
    change_counts = {
        str(beta): sum(
            r["base_pred"] != r[f"beta_{str(beta).replace('.', 'p')}"]
            for r in test_records
        )
        for beta in betas
    }
    summary = {
        "train_pseudo_query": len(y_true),
        "train_groups": len(train_groups),
        "test_groups": len(test_groups),
        "test_groups_with_context": len({r["camera_group"] for r in test_records}),
        "test_images_with_context": len(test_records),
        "test_changed_by_beta": change_counts,
        "baseline_weighted_f1": baseline["weighted_f1"],
        "best_beta": best["beta"],
        "best_weighted_f1": best["weighted_f1"],
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Temporal probability smoothing result",
        "",
        "训练侧：每个摄像头组前60%作support、后40%作query，support只使用模型概率的组内中位数，不使用query标签。",
        "测试侧：只报告无标签概率会怎样变化，不把测试结果当作提升证据。",
        "",
        f"- train pseudo-query: {len(y_true)}",
        f"- train groups: {len(train_groups)}",
        f"- test images with a context group: {len(test_records)}",
        f"- baseline pseudo-query Weighted F1: {float(baseline['weighted_f1']):.6f}",
        f"- best beta: {best['beta']}",
        f"- best pseudo-query Weighted F1: {float(best['weighted_f1']):.6f}",
        "",
        "| beta | query n | accuracy | weighted F1 | mIoU | changed |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in metric_rows:
        lines.append(
            f"| {r['beta']} | {r['query_n']} | {float(r['accuracy']):.6f} | "
            f"{float(r['weighted_f1']):.6f} | {float(r['miou']):.6f} | {r['changed_from_base']} |"
        )
    lines.extend([
        "",
        "## Test-side changes",
        "",
        json.dumps(change_counts, ensure_ascii=False),
        "",
        "若训练伪query无稳定收益，或测试侧只改变少量且没有标签证据，本路线不进入提交。",
    ])
    (out / "TEMPORAL_SMOOTHING_RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
