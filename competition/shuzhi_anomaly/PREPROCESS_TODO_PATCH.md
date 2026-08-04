# TodoList 增量修改（合并到当前 PREPROCESS_TODO）

## 已确认失败并停止

- [x] 原 `class_sequence` 永久停用：问题不仅是临时 sequence_id 粗糙，还因为算法按最少类容量截断所有类别。
- [x] 完全 1:1 `class_balanced` 停止：Weighted F1 下少数类误报严重。
- [x] 当前普通 `convnext_tiny + 全量统一 LR + 5 epoch` 不再扩展。

## 立即执行

- [ ] 用 `convnext_tiny_384`（解析为 `hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384`）加载官方 22K→1K 384 权重。
- [ ] 纯 CE 明确设 `label_smoothing=0`。
- [ ] 保存最佳 Epoch 的逐样本 OOF logits / probabilities。
- [ ] ConvNeXt 冻结特征 + Logistic Regression（none、power 0.25）。
- [ ] Fold 0 Head-only 训练。
- [ ] Fold 0 从 Head-only best 解冻最后 Stage。
- [ ] Fold 0 超过 B0 后扩展四折。
- [ ] 四折拼接 `global_oof_weighted_f1`。
- [ ] 用其他折调多数类阈值，在留出折验证。

## 并行 CPU

- [ ] 人工复核 118 张少数类及跨标签近重复。
- [ ] 完成 evidence_scale / evidence_location / scene_id。
- [ ] 如有明确改标，生成 reviewed_v2，不覆盖 raw_v1。
