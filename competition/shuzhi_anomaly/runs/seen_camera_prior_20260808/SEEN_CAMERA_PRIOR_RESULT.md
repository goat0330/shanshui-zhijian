# Seen-camera prior pseudo-query result

这是训练集内部的机位模拟诊断，不是严格GroupKFold，也不是测试集真值评估。
每个摄像头组按frame_id排序，前60%作为support，后40%作为query；support标签不使用query标签。
旧冠军OOF概率用于query，但旧冠军OOF可能已受同机位相邻帧影响，因此只能判断先验方向，不能证明隐藏集提分。

- active train with OOF: 1139
- selected camera groups: 46 (min size=4)
- pseudo-query images: 333
- baseline weighted F1: 0.983557
- best lambda by pseudo-query weighted F1: 0.0
- best weighted F1: 0.983557
- best mIoU: 0.760539

## Metrics

| lambda | n | accuracy | weighted F1 | mIoU | changed |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.05 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.1 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.2 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |
| 0.3 | 333 | 0.987988 | 0.983557 | 0.760539 | 0 |

## Decision

只有当轻量先验在这个模拟query上稳定改善、且变化集中在合理的同机位组时，才考虑对P0确认的12张测试图做局部候选。
若无改善或只改变少量样本但方向不稳定，本路线停止，不把camera prior接入提交。

## Files

- `seen_camera_prior_query.csv`: query-level predictions
- `seen_camera_prior_metrics.csv`: lambda comparison
- `seen_camera_prior_groups.csv`: selected support/query groups
