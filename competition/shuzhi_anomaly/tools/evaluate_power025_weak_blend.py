"""Screen a weak blend of the old 448 probabilities and camera power025."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


LABELS = ["乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常"]


def load(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {r["filename"]: r for r in csv.DictReader(f)}


def vector(row: dict[str, str]) -> np.ndarray:
    prefix = "prob_" if "prob_乱采" in row else "p_"
    return np.array([float(row[f"{prefix}{x}"]) for x in LABELS], dtype=np.float64)


def metrics(truth: list[int], pred: list[int]) -> tuple[float, float, float]:
    cm = np.zeros((6, 6), dtype=np.int64)
    for t, p in zip(truth, pred):
        cm[t, p] += 1
    supports = cm.sum(axis=1)
    f1, iou = [], []
    for i in range(6):
        tp = float(cm[i, i])
        fp = float(cm[:, i].sum() - tp)
        fn = float(cm[i, :].sum() - tp)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
        union = tp + fp + fn
        iou.append(tp / union if union else 0.0)
    n = len(truth)
    return (
        float(np.trace(cm) / n) if n else 0.0,
        float(sum(a * b for a, b in zip(f1, supports)) / n) if n else 0.0,
        float(np.mean([x for x, s in zip(iou, supports) if s])) if n else 0.0,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-oof", required=True)
    ap.add_argument("--power-oof", required=True)
    ap.add_argument("--base-test", required=True)
    ap.add_argument("--power-test", required=True)
    ap.add_argument("--overlap", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    base_oof = load(Path(args.base_oof))
    power_oof = load(Path(args.power_oof))
    common = sorted(set(base_oof) & set(power_oof))
    truth = [{"乱采": 0, "乱建": 1, "乱堆": 2, "乱占": 3, "有漂浮物": 4, "正常": 5}[base_oof[x]["true_label"]]
             for x in common]
    base_train = [vector(base_oof[x]) for x in common]
    power_train = [vector(power_oof[x]) for x in common]

    base_test = load(Path(args.base_test))
    power_test = load(Path(args.power_test))
    test_common = sorted(set(base_test) & set(power_test))
    overlap = {}
    with Path(args.overlap).open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            overlap[r.get("filename") or r.get("test_filename")] = r
    weights = [0.0, 0.05, 0.10, 0.20, 0.30, 0.50]
    rows = []
    for w in weights:
        preds = [int(np.argmax((1 - w) * a + w * b)) for a, b in zip(base_train, power_train)]
        acc, wf1, miou = metrics(truth, preds)
        test_preds = [int(np.argmax((1 - w) * vector(base_test[x]) + w * vector(power_test[x])))
                      for x in test_common]
        base_preds = [int(np.argmax(vector(base_test[x]))) for x in test_common]
        changed = [x for x, a, b in zip(test_common, base_preds, test_preds) if a != b]
        status_counts = {}
        for x in changed:
            status = overlap.get(x, {}).get("status", "unmapped")
            status_counts[status] = status_counts.get(status, 0) + 1
        rows.append({
            "power_weight": w,
            "oof_n": len(common),
            "oof_accuracy": acc,
            "oof_weighted_f1": wf1,
            "oof_miou": miou,
            "test_n": len(test_common),
            "test_changed": len(changed),
            "test_changed_status": json.dumps(status_counts, ensure_ascii=False),
            "test_changed_files": ",".join(changed),
        })

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "weak_blend_metrics.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    best = max(rows, key=lambda x: float(x["oof_weighted_f1"]))
    report = [
        "# Power025 weak blend screen",
        "",
        "这是内部短筛，不是平台成绩。原 448 概率作为 base，camera power025 概率按 power_weight 做线性融合。",
        "OOF只使用两份文件的共同样本；测试侧没有真值，只统计预测变化和P0重叠状态。",
        "",
        f"- common OOF: {len(common)}",
        f"- common test: {len(test_common)}",
        f"- best OOF weight: {best['power_weight']}",
        f"- best OOF Weighted F1: {float(best['oof_weighted_f1']):.6f}",
        "",
        "| power weight | OOF n | OOF Weighted F1 | OOF mIoU | test changed |",
        "|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        report.append(
            f"| {r['power_weight']} | {r['oof_n']} | {float(r['oof_weighted_f1']):.6f} | "
            f"{float(r['oof_miou']):.6f} | {r['test_changed']} |"
        )
    report.extend([
        "",
        "结论：只有在OOF不下降且测试变化具有可解释的机位依据时，才考虑平台候选；不能把测试预测数量变化当作真值提升。",
    ])
    (out / "WEAK_BLEND_RESULT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"best": best, "rows": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
