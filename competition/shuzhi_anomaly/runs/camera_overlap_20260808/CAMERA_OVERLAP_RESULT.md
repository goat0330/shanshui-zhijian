# Train/Test camera overlap CPU result

本轮只做 train/test 摄像头重叠候选分析，不修改标签、Fold、权重或提交结果。

- active train images: 1139
- test images: 695
- reviewed camera groups: 508
- confirmed train/test shared groups: 4
- confirmed shared-group test images: 12
- status counts: {'unseen_candidate': 643, 'seen_direct_group': 12, 'visual_overlap_possible': 36, 'visual_overlap_candidate': 4}

## Confirmed shared groups

camera_group_v2_0182, camera_group_v2_0183, camera_group_v2_0370, camera_group_v2_0458

## Interpretation

`seen_direct_group` comes from the reviewed camera manifest and is the only confirmed overlap signal.
`visual_overlap_candidate` and `visual_overlap_possible` are CPU image-similarity candidates only; they require manual or downstream paired validation before routing.
The next experiment should keep the old 86.77 model as the default and test any camera prior only on confirmed or high-confidence seen groups.
