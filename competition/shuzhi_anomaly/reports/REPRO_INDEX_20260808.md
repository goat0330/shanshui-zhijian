# 2026-08-08 结果与代码索引

本次 main 同步只收录轻量、可检索的代码、配置、指标和报告；训练图片、视频、权重、CAM图片和临时运行目录不进入 Git。

## 当前提交

- [当前状态与分辨率结论](CURRENT_STATUS_20260808.md)
- [power025 alpha25 线上候选分析](../runs/luna_next_route_20260808/report.md)
- [power025 结果说明](../runs/CAMERA_GROUP_V2_POWER025_RESULT_20260808.md)
- [camera v1/v2 对照](../runs/CAMERA_GROUP_V1_V2_PAIRED_COMPARISON_20260808.md)

## 已同步的验证报告

- [512px 短筛](../runs/dual_route_20260805/DEEPSEEK/README.md)
- [Copy-Paste 四折](../runs/copy_paste_448_4fold_20260806/COPY_PASTE_4FOLD_RESULT.md)
- [Copy-Paste 短训](../runs/copy_paste_448_short_20260806/COPY_PASTE_SHORT_TRAIN_RESULT.md)
- [五场景留出](../runs/scene_holdout_448_v2_20260807/SCENE_HOLDOUT_RESULT.md)
- [分类头 bake-off](../runs/head_bakeoff_448_20260807/RESULT.md)
- [DINOv2 配对指标](../runs/dinov2_vits14_448_screen/paired_oof/global_oof_metrics.json)
- [SigLIP2 教师指标](../runs/siglip2_teacher_20260806/siglip2_teacher_metrics.json)
- [MIVIA/场景适配结果](../runs/adapter_scene_20260807/adapter_scene_results.json)

## Camera-aware 路线

- [训练/测试摄像头重叠](../runs/camera_overlap_20260808/CAMERA_OVERLAP_RESULT.md)
- [Seen-camera prior](../runs/seen_camera_prior_20260808/SEEN_CAMERA_PRIOR_RESULT.md)
- [Temporal smoothing](../runs/temporal_smoothing_20260808/TEMPORAL_SMOOTHING_RESULT.md)
- [power025 弱融合](../runs/power025_weak_blend_20260808/WEAK_BLEND_RESULT.md)

## 可复用代码

- `train_classifier.py`：训练主脚本；
- `infer_ensemble.py`：四折推理与概率导出；
- `tools/build_camera_groups_v2_reviewed.py`：摄像头组构建；
- `tools/analyze_train_test_camera_overlap.py`：摄像头重叠分析；
- `tools/evaluate_seen_camera_prior.py`：seen-camera 先验诊断；
- `tools/evaluate_temporal_prob_smoothing.py`：时间概率平滑诊断；
- `tools/evaluate_power025_weak_blend.py`：模型弱融合诊断。
