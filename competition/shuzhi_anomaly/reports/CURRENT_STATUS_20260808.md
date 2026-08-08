# 赛题三当前主线状态（2026-08-08）

## 当前提交结论

- 正式平台冠军：`448px reviewed_v2 + prior_alpha5`，平台得分 **86.77**。
- 最新 `448px power025 + prior_alpha25` 候选：平台得分 **83.89**，停止使用。
- 当前默认提交仍为 86.77 候选；本轮未生成新的平台包。

## 最新 pipeline

当前主线保留：

- `train_classifier.py`：ConvNeXt-Tiny 448/384 训练、copy-paste 候选接入、scene-group sampler。
- `infer_ensemble.py`：四折等权推理，并支持导出逐图概率 CSV。
- `tools/build_camera_groups_v2_reviewed.py`：复核后的摄像头组构建。
- `tools/analyze_train_test_camera_overlap.py`：训练/测试摄像头重叠候选分析。
- `tools/evaluate_seen_camera_prior.py`：seen-camera pseudo-query 先验测试。
- `tools/evaluate_temporal_prob_smoothing.py`：同摄像头时间概率平滑短筛。
- `tools/evaluate_power025_weak_blend.py`：448 与 power025 弱融合短筛。

没有把测试集标签写回训练，也没有把探索性模型替换为正式冠军。

## 关键实验判定

| 路线 | 结果 | 决策 |
|---|---|---|
| 512px Fold1+3 | 未超过448；Fold3将 `02122.jpg` 从乱堆变为乱采 | 停止普通升分辨率 |
| Copy-Paste四折 | Weighted F1 `+0.000862`，但 mIoU `-0.001144`，乱堆F1下降 | 不替换 |
| DINOv2-S/14 | 配对 OOF 低于448基线 | 停止 |
| SigLIP2零样本 | 类别塌缩，不能直接用于六分类 | 停止 |
| power025全量替换 | 平台 `83.89`，低于冠军 `86.77` | 停止 |
| camera prior/时间平滑/弱融合 | 未产生稳定正向改变 | 不接入提交 |

## Camera route 结果

P0 分析确认：695张测试图中只有12张属于已确认的训练/测试共享摄像头组；另有4张视觉近邻候选和36张弱候选，不能自动当作 seen-camera。

因此不能用“全量测试集都是已见摄像头”解释平台分数。直接把 camera prior 或 temporal smoothing 接入提交没有证据，已停止。

## 高分辨率判断

普通512/576/640仍可能在理论上改善非常小的目标，但当前证据不支持继续投入：

1. 512短筛未超过448；
2. CAM复核显示乱堆主要问题是背景捷径和跨场景泛化，不是单纯像素不足；
3. 2×2局部块、ROI辅助训练也没有形成稳定收益；
4. 448冠军已经在平台上达到86.77，升分辨率会同时改变类别边界，存在破坏乱占、乱采和乱堆的风险。

只有在引入新的机制时才值得再测高分辨率，例如“全图448 + 有定位监督的目标裁剪”，而不是直接把整图改成512。当前不启动新的512/576/640全量训练。

## 下一步建议

最高收益仍是补充不同地点、机位和目标形态的官方口径乱堆样本，并用完整场景留出裁判。外部数据只适合小规模补充难负样本，不应直接改成比赛六类标签。
