# 11 张少数类人工复核方法

## 复核对象

本包只包含当前四折 OOF 中未被模型正确识别的 11 张尾类样本：

- `乱建`：`02486.jpg`、`02487.jpg`、`02488.jpg`、`02489.jpg`
- `正常`：`00033.jpg`、`00064.jpg`、`00096.jpg`、`00100.jpg`、`00114.jpg`、`01086.jpg`、`02111.jpg`

`official_label` 是 `train.json` 的官方标签，`model_pred` 只是模型参考，不能代替人工判断。

## 逐张复核步骤

1. 先看整图，不根据模型预测先入为主。
2. 再看局部证据：建筑、堆料、占用岸线、采砂机械、漂浮物及正常设施。
3. 判断该证据是局部目标还是整幅场景关系。
4. 判断是否同时存在漂浮物；记录是否影响主标签。
5. 检查是否像同一视频/机位/河段的连续帧，并填写 `same_scene_group`。
6. 最后填写 `reviewed_label`、`review_status`、`confidence` 和 `review_notes`。

## 字段约束

- `reviewed_label` 只能填：`乱采`、`乱建`、`乱堆`、`乱占`、`有漂浮物`、`正常`。
- `review_status` 只能填：`confirmed`、`relabel`、`uncertain`、`exclude_from_strict_validation`。
- 没有明确视觉证据时，保留 `official_label`，填 `uncertain`，不要强行改标。
- `evidence_scale` 填 `local`、`global` 或 `none`。
- `has_floating_object` 填 `yes`、`no` 或 `unclear`。
- `confidence` 填 `high`、`medium` 或 `low`。

## 数据保护规则

本次复核只能修改模板文件：

```text
review_decisions_v2.csv
```

不得修改：

```text
原始 train.json
raw_v1
reviewed_v1
```

人工复核完成后，先检查 CSV 字段和六类标签，再生成 `train_reviewed_v2.json`，并使用现有 OOF 概率重新计算指标。不要直接重新训练。

## 复核后的决策门

- 0～少量明确改标：保留当前主模型，比较 `raw_v1` 与 `reviewed_v2` 的 OOF 指标。
- 明确改标 5～20 张：只做冻结 Backbone 的 Head 小规模对照。
- 发现多个同场景跨 Fold：先建立 `cv_v2_scene_group`，不要直接重跑四折。
- 无法判断：保留官方标签并标记 `uncertain`。
