# 六分类官方标签复核口径

P0 只遵循赛事提供的六个标签，不新增类别、不合并类别、不凭个人理解改写 `train.json`。

官方标签固定为：

```text
乱采
乱建
乱堆
乱占
有漂浮物
正常
```

## P0 处理规则

1. `original_label` 读取自官方 `train.json`。
2. `reviewed_label` 默认保留 `original_label`。
3. 没有明确证据时不擅自改成其他标签，记录为待视觉复核。
4. `alternate_label` 只有在人工发现明确冲突时填写。
5. P0 不修改原始 `train.json`；`train_reviewed_v1.json` 是可追溯的官方标签副本。
6. `evidence_scale` 和 `evidence_location` 只记录图像证据尺度，不改变官方类别含义。

当前 `review_decisions.csv` 的 `manual_visual_review=false`，表示官方标签已透传，但图片语义人工复核尚未完成；不能把它误读为已经完成人工改标。
