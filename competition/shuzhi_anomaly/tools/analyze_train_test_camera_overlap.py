"""Small CPU check for train/test camera overlap candidates.

The reviewed camera manifest remains the source of truth for confirmed overlap.
Image similarity is only a candidate signal; it never changes labels or routes
test predictions by itself.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def image_path(source_root: Path, row: dict[str, str]) -> Path:
    return source_root / Path(row["relative_path"])


def read_image(path: Path, flags: int) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, flags) if data.size else None


def thumbnail(path: Path) -> np.ndarray:
    image = read_image(path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot decode {path}")
    image = cv2.resize(image, (48, 36), interpolation=cv2.INTER_AREA)
    vector = image.astype(np.float32).reshape(-1)
    vector -= vector.mean()
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 1e-6 else vector


def sift_match(query_path: Path, train_path: Path, sift: cv2.SIFT) -> tuple[int, int, float]:
    query = read_image(query_path, cv2.IMREAD_GRAYSCALE)
    train = read_image(train_path, cv2.IMREAD_GRAYSCALE)
    if query is None or train is None:
        return 0, 0, 0.0
    query = cv2.resize(query, (640, 480), interpolation=cv2.INTER_AREA)
    train = cv2.resize(train, (640, 480), interpolation=cv2.INTER_AREA)
    kp_q, desc_q = sift.detectAndCompute(query, None)
    kp_t, desc_t = sift.detectAndCompute(train, None)
    if desc_q is None or desc_t is None or len(desc_q) < 2 or len(desc_t) < 2:
        return 0, 0, 0.0
    matches = cv2.BFMatcher(cv2.NORM_L2).knnMatch(desc_q, desc_t, k=2)
    good = [first for first, second in matches if first.distance < 0.75 * second.distance]
    if len(good) < 4:
        return len(good), 0, 0.0
    points_q = np.float32([kp_q[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    points_t = np.float32([kp_t[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(points_q, points_t, cv2.RANSAC, 5.0)
    inliers = int(mask.sum()) if mask is not None else 0
    return len(good), inliers, inliers / max(len(good), 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--camera-manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--sift-k", type=int, default=3)
    parser.add_argument("--sift-threshold", type=float, default=0.95)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_csv(args.camera_manifest.resolve())
    train_rows = [row for row in rows if row["split"] == "train" and row["enabled_for_cv"] == "yes"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if not train_rows or not test_rows:
        raise ValueError("camera manifest must contain active train rows and test rows")

    source_root = (
        args.source_root.resolve()
        if args.source_root is not None
        else Path.cwd().parents[1] / "水域综合异常识别_训练集+验证集"
    )
    if not source_root.exists():
        raise ValueError(f"source root does not exist: {source_root}")
    train_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    test_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in train_rows:
        train_groups[row["camera_group"]].append(row)
    for row in test_rows:
        test_groups[row["camera_group"]].append(row)
    direct_test_names = {
        row["filename"]
        for row in test_rows
        if row["camera_group"] in train_groups
    }

    train_vectors = np.stack([thumbnail(image_path(source_root, row)) for row in train_rows])
    test_vectors = np.stack([thumbnail(image_path(source_root, row)) for row in test_rows])
    cosine = test_vectors @ train_vectors.T
    sift = cv2.SIFT_create(nfeatures=500)
    match_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for test_index, test_row in enumerate(test_rows):
        candidate_indices = np.argsort(cosine[test_index])[::-1][: max(args.top_k, args.sift_k)]
        best_index = int(candidate_indices[0])
        best_visual: dict[str, object] = {
            "test_filename": test_row["filename"],
            "test_camera_group": test_row["camera_group"],
            "rank": 1,
            "train_filename": train_rows[best_index]["filename"],
            "train_camera_group": train_rows[best_index]["camera_group"],
            "train_label": train_rows[best_index]["label"],
            "thumbnail_cosine": f"{float(cosine[test_index, best_index]):.6f}",
            "sift_good": 0,
            "homography_inliers": 0,
            "homography_inlier_ratio": "0.0000",
            "visual_score": float(cosine[test_index, best_index]),
        }
        direct = test_row["filename"] in direct_test_names
        top_cosine = float(cosine[test_index, best_index])
        sift_indices = candidate_indices[: args.sift_k] if direct or top_cosine >= args.sift_threshold else []
        for rank, train_index in enumerate(sift_indices, start=1):
            train_row = train_rows[int(train_index)]
            good, inliers, inlier_ratio = sift_match(
                image_path(source_root, test_row), image_path(source_root, train_row), sift
            )
            record = {
                "test_filename": test_row["filename"],
                "test_camera_group": test_row["camera_group"],
                "rank": rank,
                "train_filename": train_row["filename"],
                "train_camera_group": train_row["camera_group"],
                "train_label": train_row["label"],
                "thumbnail_cosine": f"{float(cosine[test_index, train_index]):.6f}",
                "sift_good": good,
                "homography_inliers": inliers,
                "homography_inlier_ratio": f"{inlier_ratio:.4f}",
            }
            match_rows.append(record)
            score = (float(cosine[test_index, train_index]) + min(inlier_ratio, 1.0)) / 2.0
            if score > float(best_visual["visual_score"]):
                best_visual = {
                    **record,
                    "visual_score": score,
                }
        cosine_value = float(best_visual["thumbnail_cosine"])
        inliers = int(best_visual["homography_inliers"])
        inlier_ratio = float(best_visual["homography_inlier_ratio"])
        visual_candidate = cosine_value >= 0.90 or (inliers >= 10 and inlier_ratio >= 0.35)
        visual_possible = cosine_value >= 0.84 or (inliers >= 6 and inlier_ratio >= 0.25)
        if direct:
            status = "seen_direct_group"
        elif visual_candidate:
            status = "visual_overlap_candidate"
        elif visual_possible:
            status = "visual_overlap_possible"
        else:
            status = "unseen_candidate"
        summary_rows.append(
            {
                "test_filename": test_row["filename"],
                "test_camera_group": test_row["camera_group"],
                "status": status,
                "direct_train_test_group": "yes" if direct else "no",
                "best_train_filename": best_visual["train_filename"],
                "best_train_camera_group": best_visual["train_camera_group"],
                "best_train_label": best_visual["train_label"],
                "thumbnail_cosine": best_visual["thumbnail_cosine"],
                "sift_good": best_visual["sift_good"],
                "homography_inliers": best_visual["homography_inliers"],
                "homography_inlier_ratio": best_visual["homography_inlier_ratio"],
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "camera_overlap_test.csv", summary_rows)
    write_csv(args.out_dir / "camera_overlap_top_matches.csv", match_rows)
    status_counts = Counter(row["status"] for row in summary_rows)
    direct_groups = sorted({row["camera_group"] for row in test_rows if row["filename"] in direct_test_names})
    report = [
        "# Train/Test camera overlap CPU result",
        "",
        "本轮只做 train/test 摄像头重叠候选分析，不修改标签、Fold、权重或提交结果。",
        "",
        f"- active train images: {len(train_rows)}",
        f"- test images: {len(test_rows)}",
        f"- reviewed camera groups: {len(set(row['camera_group'] for row in rows))}",
        f"- confirmed train/test shared groups: {len(direct_groups)}",
        f"- confirmed shared-group test images: {len(direct_test_names)}",
        f"- status counts: {dict(status_counts)}",
        "",
        "## Confirmed shared groups",
        "",
        ", ".join(direct_groups) if direct_groups else "none",
        "",
        "## Interpretation",
        "",
        "`seen_direct_group` comes from the reviewed camera manifest and is the only confirmed overlap signal.",
        "`visual_overlap_candidate` and `visual_overlap_possible` are CPU image-similarity candidates only; they require manual or downstream paired validation before routing.",
        "The next experiment should keep the old 86.77 model as the default and test any camera prior only on confirmed or high-confidence seen groups.",
    ]
    (args.out_dir / "CAMERA_OVERLAP_RESULT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"active_train": len(train_rows), "test": len(test_rows), "shared_groups": len(direct_groups), "shared_test": len(direct_test_names), "status": dict(status_counts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
