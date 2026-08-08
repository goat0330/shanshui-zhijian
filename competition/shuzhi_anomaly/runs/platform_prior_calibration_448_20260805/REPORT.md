# 448px 乱堆先验候选扫描

日期：2026-08-05

## 输入

- 448px OOF：`runs/pile_core_20260804/fusion_eval_real/oof_448_full_reviewed_v2.csv`
- 448px 测试概率：`runs/pile_core_20260804/gpu_probs/test_probs_448.csv`
- 测试图片：695张；本轮只生成内部候选，不上传平台。

## OOF结论

原始448 OOF：Weighted F1 `0.984696`，mIoU `0.644923`，乱堆F1 `0.978723`。

全局乘以乱堆概率的 alpha 在 `0.75–2.0` 时不改变预测；alpha=3开始增加误报，Weighted F1降至约`0.984681`，mIoU降至约`0.640973`。强制额外增加1张乱堆预测也下降，因此不能用全局配额直接选参数。

## 已生成候选

```text
alpha=3  -> 乱堆8张
alpha=5  -> 乱堆13张
alpha=7  -> 乱堆14张
alpha=10 -> 乱堆17张
```

候选均为695条、格式合规；仅作为平台黑盒对照，不代表模型真实提升。
