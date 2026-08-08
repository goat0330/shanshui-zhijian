"""Evaluate a lightweight camera-group prior on a train-only pseudo-query.

This is a diagnostic, not a production router.  For each sufficiently large
camera group, earlier frames provide the support labels and later frames are
the query.  The old champion OOF probabilities are adjusted with a smoothed
support-vs-global class prior and evaluated against the manifest labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


LABELS = ["乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常"]
LABEL_TO_ID = {name: i for i, name in enumerate(LABELS)}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def frame_key(row: dict[str, str]) -> tuple[int, str]:
    raw = (row.get("frame_id") or "").strip()
    try:
        return int(float(raw)), row["filename"]
    except ValueError:
        digits = "".join(ch for ch in row["filename"] if ch.isdigit())
        return (int(digits) if digits else 10**12), row["filename"]


def softmax_log_adjustment(prob: np.ndarray, support_counts: np.ndarray,
                           global_counts: np.ndarray, lam: float) -> int:
    eps = 1e-8
    support_prior = (support_counts + 1.0) / (support_counts.sum() + len(LABELS))
    global_prior = (global_counts + 1.0) / (global_counts.sum() + len(LABELS))
    score = np.log(np.maximum(prob, eps)) + lam * (
        np.log(support_prior) - np.log(global_prior)
    )
    return int(np.argmax(score))


def metrics(y_true: list[int], y_pred: list[int]) -> dict[str, float | int]:
    n = len(y_true)
    if not n:
        return {"n": 0, "accuracy": None, "weighted_f1": None, "miou": None}
    cm = np.zeros((len(LABELS), len(LABELS)), dtype=np.int64)
    for truth, pred in zip(y_true, y_pred):
        cm[truth, pred] += 1
    f1s: list[float] = []
    ious: list[float] = []
    supports: list[int] = []
    for i in range(len(LABELS)):
        tp = float(cm[i, i])
        fp = float(cm[:, i].sum() - cm[i, i])
        fn = float(cm[i, :].sum() - cm[i, i])
        support = int(cm[i, :].sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall)
                   if precision + recall else 0.0)
        union = tp + fp + fn
        ious.append(tp / union if union else 0.0)
        supports.append(support)
    total_support = sum(supports)
    weighted_f1 = sum(f * s for f, s in zip(f1s, supports)) / total_support
    present_ious = [iou for iou, support in zip(ious, supports) if support > 0]
    return {
        "n": n,
        "accuracy": float(np.trace(cm) / n),
        "weighted_f1": float(weighted_f1),
        "miou": float(sum(present_ious) / len(present_ious)),
        "per_class_f1": f1s,
        "per_class_recall": [
            float(cm[i, i] / cm[i, :].sum()) if cm[i, :].sum() else 0.0
            for i in range(len(LABELS))
        ],
        "confusion_matrix": cm.tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-manifest", required=True)
    parser.add_argument("--oof", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--min-group-size", type=int, default=4)
    parser.add_argument("--support-fraction", type=float, default=0.6)
    args = parser.parse_args()

    manifest_rows = read_csv(Path(args.camera_manifest))
    oof_rows = read_csv(Path(args.oof))
    oof_by_filename = {row["filename"]: row for row in oof_rows}

    rows_by_group: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    global_counts = np.zeros(len(LABELS), dtype=np.float64)
    for row in manifest_rows:
        if row.get("split") != "train" or row.get("enabled_for_cv", "yes").lower() != "yes":
            continue
        if row["filename"] not in oof_by_filename:
            continue
        if row.get("label") not in LABEL_TO_ID:
            continue
        rows_by_group[row["camera_group"]].append(row)
        global_counts[LABEL_TO_ID[row["label"]]] += 1

    lambdas = [0.0, 0.05, 0.10, 0.20, 0.30]
    records: list[dict[str, str | int | float]] = []
    selected_groups: list[dict[str, int | str]] = []
    for group, rows in sorted(rows_by_group.items()):
        rows = sorted(rows, key=frame_key)
        n = len(rows)
        if n < args.min_group_size:
            continue
        support_n = int(round(n * args.support_fraction))
        support_n = max(2, min(support_n, n - 2))
        support = rows[:support_n]
        query = rows[support_n:]
        support_counts = np.zeros(len(LABELS), dtype=np.float64)
        for row in support:
            support_counts[LABEL_TO_ID[row["label"]]] += 1
        selected_groups.append({
            "camera_group": group,
            "support_count": len(support),
            "query_count": len(query),
            "total_count": n,
            "support_class_count": int(np.count_nonzero(support_counts)),
        })
        for row in query:
            oof = oof_by_filename[row["filename"]]
            probs = np.array([float(oof[f"prob_{label}"]) for label in LABELS], dtype=np.float64)
            base_pred = int(np.argmax(probs))
            item: dict[str, str | int | float] = {
                "filename": row["filename"],
                "camera_group": group,
                "frame_id": row.get("frame_id", ""),
                "support_count": len(support),
                "query_true_label": row["label"],
                "query_true_id": LABEL_TO_ID[row["label"]],
                "base_pred": LABELS[base_pred],
                "base_pred_id": base_pred,
            }
            for lam in lambdas:
                pred = softmax_log_adjustment(probs, support_counts, global_counts, lam)
                suffix = str(lam).replace(".", "p")
                item[f"prior_{suffix}"] = LABELS[pred]
                item[f"prior_{suffix}_id"] = pred
            records.append(item)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    query_path = out_dir / "seen_camera_prior_query.csv"
    if records:
        fieldnames = list(records[0].keys())
        with query_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
    else:
        query_path.write_text("filename\n", encoding="utf-8-sig")

    y_true = [int(r["query_true_id"]) for r in records]
    metric_rows: list[dict[str, str | int | float | None]] = []
    for lam in lambdas:
        suffix = str(lam).replace(".", "p")
        key = "base_pred_id" if lam == 0.0 else f"prior_{suffix}_id"
        result = metrics(y_true, [int(r[key]) for r in records])
        metric_rows.append({
            "lambda": lam,
            "n": result["n"],
            "accuracy": result["accuracy"],
            "weighted_f1": result["weighted_f1"],
            "miou": result["miou"],
            "changed_from_base": sum(
                int(r[key]) != int(r["base_pred_id"]) for r in records
            ),
            "per_class_f1": json.dumps(result.get("per_class_f1", []), ensure_ascii=False),
            "per_class_recall": json.dumps(result.get("per_class_recall", []), ensure_ascii=False),
        })
    metric_path = out_dir / "seen_camera_prior_metrics.csv"
    with metric_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metric_rows)

    selected_group_path = out_dir / "seen_camera_prior_groups.csv"
    with selected_group_path.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["camera_group", "support_count", "query_count", "total_count", "support_class_count"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected_groups)

    best = max(
        metric_rows,
        key=lambda row: -1.0 if row["weighted_f1"] is None else float(row["weighted_f1"]),
    )
    baseline = metric_rows[0]
    report = [
        "# Seen-camera prior pseudo-query result",
        "",
        "这是训练集内部的机位模拟诊断，不是严格GroupKFold，也不是测试集真值评估。",
        "每个摄像头组按frame_id排序，前60%作为support，后40%作为query；support标签不使用query标签。",
        "旧冠军OOF概率用于query，但旧冠军OOF可能已受同机位相邻帧影响，因此只能判断先验方向，不能证明隐藏集提分。",
        "",
        f"- active train with OOF: {int(global_counts.sum())}",
        f"- selected camera groups: {len(selected_groups)} (min size={args.min_group_size})",
        f"- pseudo-query images: {len(records)}",
        f"- baseline weighted F1: {float(baseline['weighted_f1']):.6f}",
        f"- best lambda by pseudo-query weighted F1: {best['lambda']}",
        f"- best weighted F1: {float(best['weighted_f1']):.6f}",
        f"- best mIoU: {float(best['miou']):.6f}",
        "",
        "## Metrics",
        "",
        "| lambda | n | accuracy | weighted F1 | mIoU | changed |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metric_rows:
        report.append(
            f"| {row['lambda']} | {row['n']} | {float(row['accuracy']):.6f} | "
            f"{float(row['weighted_f1']):.6f} | {float(row['miou']):.6f} | {row['changed_from_base']} |"
        )
    report.extend([
        "",
        "## Decision",
        "",
        "只有当轻量先验在这个模拟query上稳定改善、且变化集中在合理的同机位组时，才考虑对P0确认的12张测试图做局部候选。",
        "若无改善或只改变少量样本但方向不稳定，本路线停止，不把camera prior接入提交。",
        "",
        "## Files",
        "",
        f"- `{query_path.name}`: query-level predictions",
        f"- `{metric_path.name}`: lambda comparison",
        f"- `{selected_group_path.name}`: selected support/query groups",
    ])
    (out_dir / "SEEN_CAMERA_PRIOR_RESULT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    summary = {
        "active_train_with_oof": int(global_counts.sum()),
        "selected_groups": len(selected_groups),
        "pseudo_query": len(records),
        "baseline_weighted_f1": baseline["weighted_f1"],
        "best_lambda": best["lambda"],
        "best_weighted_f1": best["weighted_f1"],
        "best_miou": best["miou"],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
