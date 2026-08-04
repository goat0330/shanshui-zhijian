# 赛题三：六分类训练 TodoList（当前版）

## 统一口径

- 单张 JPG/PNG 图片输出一个官方六分类 `label`。
- 官方标签固定为：`乱采`、`乱建`、`乱堆`、`乱占`、`有漂浮物`、`正常`。
- 主指标：Weighted F1；辅助指标：全量 OOF Macro-F1、Accuracy、Balanced Accuracy、六类 mIoU、每类 F1、混淆矩阵。
- 原始 `train.json` 和原图只读，不覆盖、不删除、不改名。
- 数据版本：`raw_v1` 保留官方原始标签；`reviewed_v1` 当前是官方标签透传副本，尚未发生语义改标。

## 当前诊断结论（2026-08-04）

- 数据清单、标签版本、4-fold 工程验证和提交校验已完成；模型的有效六分类能力尚未建立。
- 原始 1,144 张标签计数为：`有漂浮物 1,026`、`乱占 60`、`乱采 24`、`乱堆 23`、`正常 7`、`乱建 4`。去除精确重复后，当前 `train_index.csv` 实际使用 1,139 张。
- 4-fold 当前配置的 Weighted F1 均值 `0.8474`，与 B0 常数预测 `0.847430` 基本相同；Macro-F1 `0.1576`、mIoU `0.1569`，说明模型主要复现类别先验。
- 这轮不能表述为“ConvNeXt 无效”，准确表述是：当前初始化、损失、训练策略和训练时长没有让模型学到六类边界。
- 当前本机 `timm 1.0.28` 的 `convnext_tiny` 实际预训练配置为 `timm/convnext_tiny.in12k_ft_in1k`、默认输入 224；尚未验证目标的 `convnext_tiny.fb_in22k_ft_in1k_384`。目标权重在 Hugging Face 官方仓库存在，但本机注册表不列出时必须用 `hf-hub:` 前缀加载并验收。
- 当前默认 `label_smoothing=0.03`，所以已完成基线严格来说是 `CE + Label Smoothing 0.03`，不是纯 CE；同时全部 Backbone 使用统一学习率直接训练，尚未执行冻结分类头和分层解冻。
- 当前 `sequence_id` 只有 5 个粗粒度 `file_block`，原 `class_sequence` 还按最少类容量截断，永久停用；真实 `sequence_id` 主要用于防泄漏分组，不是极端类别不平衡的直接解法。
- 当前 `class_balanced` 使用 `1/count` 过强，已证明会造成少数类误报；后续若需要采样，只允许固定 epoch 长度、`count^-α` 温和采样并限制尾类重复。
- 当前旧验证只保存混淆矩阵和 Argmax；修复包 v2 已补齐逐样本 OOF logits/probabilities，并完成四折汇总。
- 修复包 v2 的四折 Last-stage 已完成：Global OOF Weighted F1 `0.979403`、Macro-F1 `0.647091`、mIoU `0.629527`，相对 B0 的 Weighted F1 `0.847430` 和 mIoU `0.1569` 有明显提升；这仍是当前 `duplicate_near` 内部验证，不等同于隐藏集成绩。
- 重要剩余问题：全量 OOF 仍未预测出 `乱建`（4 张）和 `正常`（7 张），二者 IoU 均为 0；因此当前模型虽已不再是多数类常数基线，但少数类能力仍不完整。
- 交叉拟合多数类阈值的 Weighted F1 `0.977779`、mIoU `0.625159`，低于原始 Argmax OOF；阈值校准暂不作为主提交策略。

## P0：已完成，可并行启动 GPU

- [x] 扫描 1,839 张支持格式图片：训练 1,144，测试 695。
- [x] 解释 691/695：691 张 JPG + 4 张 PNG，不再漏掉 PNG。
- [x] 解码失败 0；尺寸不一致 4 张，已单独列为待确认项。
- [x] SHA-256、dHash、精确重复、近重复候选和非破坏性训练索引。
- [x] 固定 `config/label_map.json`，训练/验证/OOF/提交使用同一标签顺序。
- [x] 生成 `train_manifest_v1.csv`、`test_manifest_v1.csv` 及 SHA-256。
- [x] 生成 241 张复核记录，其中少数类 118 张是优先项。
- [x] 按官方标签生成 `review_decisions.csv` 和 `train_reviewed_v1.json`；改标数量为 0，未伪造人工视觉复核结果。
- [x] 生成 B0/B1/B2 常数基线；B0 全量 OOF Weighted F1 为 **0.847430**。
- [x] 用 B0 生成并校验 695 条提交结果 `submission_b0.json`。
- [x] 内部 `duplicate_near` 4-fold：精确重复跨折 0，近重复跨折 0。

## P0 后续 CPU：与 GPU 并行

- [ ] 如要做真正视觉复核，打开 `generated/label_review_candidates.csv` 对前 118 张逐张确认；只在有明确证据时修改 `reviewed_label`。
- [ ] 重点查看跨标签近重复和连续帧标签变化；没有明确证据则保留官方标签。
- [ ] 确认 4 张尺寸不一致图片：`02486–02489.jpg`，明确训练和提交使用实际尺寸还是官方元数据尺寸。
- [ ] 如果取得真实视频/来源信息，补充真实 `scene_id/sequence_id`；当前文件名序列只能用于诊断。
- [ ] 复核后如有改标，重新生成 `reviewed_v2`，并与 `raw_v1` 做同配置对照；不能覆盖当前 `reviewed_v1`。

## P1：先修复训练基础设施

- [x] 完成模型工厂、本机模型 ID 和 CUDA 环境校验；当前本机可识别 `convnext_tiny`、`efficientnetv2_rw_s`。
- [x] 用本机可用的 `convnext_tiny` 预训练权重完成冒烟和 4-fold 工程基线；该权重不是目标的 22K→1K 384 权重。
- [x] 用 `hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384` 验证目标权重：输入配置 `384×384`、`bicubic`、分类头 `6×768`；权重 SHA-256 为 `a5cbe10cfa2e90ec787a082253033ac0a61de0264b68210815a988e53a1a5d7c`。
- [x] 增加 `ImageOps.exif_transpose`；保留全图 resize + padding，不使用 CenterCrop。
- [x] 从模型读取 `timm.data.resolve_model_data_config(model)`，使用对应 interpolation、mean、std。
- [x] 增加纯 CE 参数，默认 `label_smoothing=0、logit_adjustment=0`；尚未完成纯 CE 正式训练。
- [x] 验证过程支持 `filename、fold、true_label、pred_label、logits、probabilities、epoch、checkpoint`，尚未生成新的全量 OOF 产物。
- [x] 增加 AMP/autocast、梯度裁剪和 Early Stopping；只用于提速和稳定训练，不把 AMP 当作提分项。
- [x] 安装修复包 v2 的共享模型、冻结特征、OOF 汇总和交叉拟合阈值工具；已通过静态编译和入口检查。
- [x] 目标权重冻结特征自然权重全量 OOF：Weighted F1 `0.980256`，Macro-F1 `0.648480`，mIoU `0.632003`。
- [x] 目标权重冻结特征 `count^-0.25` 全量 OOF：Weighted F1 `0.982993`，Macro-F1 `0.716779`，mIoU `0.676633`。
- [x] 完成当前 3 epoch 冒烟、4-fold checkpoint、Weighted F1 和 mIoU 链路验收。

### 已完成基线结果

配置：`raw_v1 + ConvNeXt-Tiny + 384 + standard sampler + 5 epoch + Weighted F1 选模`。

- fold0：Weighted F1 `0.8475`，Macro-F1 `0.1576`，mIoU `0.1793`
- fold1：Weighted F1 `0.8567`，Macro-F1 `0.1582`，mIoU `0.1505`
- fold2：Weighted F1 `0.8416`，Macro-F1 `0.1572`，mIoU `0.1487`
- fold3：Weighted F1 `0.8440`，Macro-F1 `0.1573`，mIoU `0.1490`
- 四折均值：Weighted F1 `0.8474`，Macro-F1 `0.1576`，mIoU `0.1569`

结论：当前旧配置只用于失败诊断，不再继续延长 epoch 或重复四折。

### 单折提分试验结论

- `class_sequence + max_frames_per_sequence=1`：当前临时 `sequence_id` 只有 5 个粗粒度 `file_block`，每个 epoch 实际只抽 6 张图；即使换成真实序列，原实现仍按最少类容量截断，永久停用，不扩展四折。
- `Logit Adjustment τ=0.25`：fold0 Weighted F1 `0.8475`、mIoU `0.1793`，与标准基线相同。
- `class_balanced`：fold0 最佳 Weighted F1 `0.2167`、mIoU `0.0279`，少数类误报过多，不作为当前主路线。
- 当前旧采样和旧损失实验暂停；GPU 不暂停，改做目标强权重、冻结特征和分层解冻，CPU 同时进行人工复核。

## P2：冻结特征诊断（已完成首轮）

- [x] 目标 ConvNeXt 22K→1K 384：`num_classes=0` 提取 1,139 张训练特征，固定同一 `cv_v1_duplicate_near_4fold` 完成 Logistic Regression OOF。
- [x] 已比较自然权重和温和 `count^-0.25`；暂不测试完全 `class_weight="balanced"`，避免重复已知的激进均衡误报问题。
- [ ] EfficientNetV2-S 冻结特征 + Logistic Regression，使用完全相同 Fold 和 OOF 文件。
- [x] 输出每类 F1、mIoU、Weighted F1、混淆矩阵和逐样本概率；按全量 global OOF 决策，不按单折最好分数决策。
- [x] 冻结特征已能区分少数类，因此暂不考虑 DINOv2；下一步验证微调策略。

## P3：正确执行迁移学习

- [ ] 支持冻结 Backbone、只训练分类头和分层学习率配置；不再全部 Backbone 统一 `3e-4` 直接微调。
- [x] 阶段 A：目标强权重 + 自然采样 + 纯 CE，只训练分类头 15～30 epoch，保存逐样本 OOF；四折均已完成。
- [x] 阶段 B：加载阶段 A 最佳权重，只解冻最后一个 Stage；Backbone `1e-5～3e-5`，Head `1e-4～3e-4`，训练 10～20 epoch；四折均已完成。
- [ ] 阶段 C：只有阶段 B 稳定提升时才全量低学习率微调；启用 Early Stopping，不再用固定 5 epoch 下结论。
- [x] 每个 Fold 已保存 `best.pt`、`last.pt`、`best_metrics.json`、`history.json`、混淆矩阵和逐样本 OOF；Bad Case 汇总待补。
- [ ] 主要成绩统一使用拼接后的 `global_oof_weighted_f1`，同时保存 Fold mean/std/min 和全量 mIoU。

### Fold 0 首轮结果

- [x] Head-only 最佳：Weighted F1 `0.972566`，Macro-F1 `0.600282`，mIoU `0.659598`。
- [x] Last-stage 最佳：Weighted F1 `0.983987`，Macro-F1 `0.635611`，mIoU `0.731557`。
- [x] Last-stage 6 epoch 早停，保存 280 条验证图逐样本 OOF；目标强权重和分层微调链路通过。
- [x] Fold 1～3 已复现并拼接 1,139 条 Global OOF；Fold 0 不单独作为最终成绩。

### 四折修复包 v2 结果

| 配置 | Global Weighted F1 | Macro-F1 | mIoU | OOF |
|---|---:|---:|---:|---:|
| Head-only → Last-stage，Argmax | **0.979403** | 0.647091 | **0.629527** | 1,139 |
| 交叉拟合多数类阈值 | 0.977779 | 0.644597 | 0.625159 | 1,139 |

- Argmax 结果作为当前主结果；阈值校准没有带来提升，暂不启用。
- Global 混淆矩阵中 `乱建` 4 张、`正常` 7 张均未被预测出来；下一步优先做少数类 Bad Case/标签核查和温和 Head 重训，不直接全量解冻。

## P4：OOF 概率校准与解耦分类器

必须先完成 P1 的逐样本 OOF，再执行以下单变量实验：

- [x] 已执行修复包内交叉拟合多数类阈值；相对 Argmax 的 Weighted F1 和 mIoU 均下降，暂不作为主策略。
- [ ] 交叉拟合漂浮物阈值：3 折调 `t=0.40～0.95`，剩余 1 折验证，轮换 4 次；不能在同一 OOF 上调参并报无偏成绩。
- [ ] 交叉拟合六类小偏置校准；目标是保持漂浮物 Recall，同时减少其他五类被误报为漂浮物。
- [ ] cRT：先自然采样学习 Backbone，再冻结 Backbone 重训分类 Head；只比较自然 Head、sqrt-balanced Head、Cosine Classifier。
- [ ] 温和采样仅测试 `count^-0.25` 和 `count^-0.5`，固定 epoch 长度并限制尾类单样本重复次数；禁止原 `class_sequence` 和完全 `1/count` 均衡。
- [ ] Balanced Softmax 排在 cRT 后，仅在 OOF 结果支持时测试 `τ=0.25/0.5`。

### P4 当前对照结果

- [x] Fold 0 cRT/温和采样对照：从 Last-stage 最佳权重冻结 Backbone，使用 `count^-0.25` 重训 Head；最佳 Weighted F1 `0.983987`、mIoU `0.731557`，与自然采样 Last-stage 持平，未改善 `乱建/正常`，不扩展四折。
- [ ] 暂不测试更强的 `count^-0.5`、完全 `1/count` 或同时叠加类别损失；当前证据不足以支持更激进的方案。

每项必须在同一 `cv_v1_duplicate_near_4fold` 上比较 Weighted F1，并检查有漂浮物和少数类 F1 是否明显下降。

当前顺序：先补 P1 OOF/预处理/目标权重，再做 P2 冻结特征和 P3 分层解冻；不等待真实 `sequence_id` 才开始 GPU。

## P5：人工复核与训练并行

- [ ] 复核 118 张非漂浮物少数类：目标是否可见、证据是局部还是全局、是否需要业务背景、是否与其他类别同时出现。
- [ ] 复核跨标签近重复、连续帧标签变化和四张尺寸异常图片。
- [ ] 补充人工 `scene_id`；真实 sequence 主要用于防泄漏 Group Fold 和组内限帧，不直接用于极端均衡。
- [ ] 记录 `evidence_scale、confidence、review_notes`，形成 `reviewed_v2`；不覆盖 `reviewed_v1`。
- [ ] 用 `reviewed_v2` 与 `raw_v1` 做同一配置 OOF 对照，量化清洗收益。

## P6：全图与局部块

- [ ] 只有目标强权重和分层微调仍漏掉小目标时，才测试全图 384 + 2×2 重叠局部块 384。
- [ ] 推理阶段先搜索 global `0.6～0.8`、local `0.2～0.4`，比较 max、top-2 mean、log-sum-exp。
- [ ] 是否启用局部块必须由人工 `evidence_scale` 和 OOF Bad Case 决定；整幅场景关系不使用局部硬切。

## P7：验证和提交

- [x] B0 导出器和校验器已完成。
- [ ] 将真实模型预测接入 `export_submission.py`。
- [ ] 校验 695 张测试图片全部覆盖、无重复、无遗漏，尺寸来自冻结 Manifest，标签只能是六类之一。
- [ ] 保存 Checkpoint 列表、融合权重、Manifest SHA、环境报告和 Git commit。

## 验证命名

- `cv_v1_duplicate_near_4fold`：当前工程选模 Fold，精确/近重复不跨折；不能称为严格场景泛化。
- `cv_v2_scene_group`：真实场景/视频来源确认后建立，用于严格泛化评估；当前未就绪。
- 当前临时序列过粗，不能根据它单独宣称 Group-OOD 已完成。

## 第一轮明确不做

- 不把六分类改成二分类。
- 不使用官方无标签测试集伪标签训练。
- 不使用原 `class_sequence`，不使用完全 `1/count` 的 `class_balanced`，不继续重复当前普通 `convnext_tiny` 的 5 epoch 四折。
- 不同时叠加强均衡采样、巨大类别权重、Focal、Logit Adjustment 和 Balanced Softmax。
- 不启动 MOSS-VL 四折 LoRA、DINOv2 大规模微调或 YOLO Detection。
- YOLO-CLS 只在主模型稳定后做低成本对照。
- 不接入科大讯飞水体分割的 Mask、分割权重或脚本。

## 关键命令

```powershell
# 官方标签透传版本
python build_reviewed_labels.py

# B0完整提交校验
python export_submission.py
python validate_submission.py generated/submission_b0.json

# 纯 CE 基线：必须显式关闭默认的 Label Smoothing 和 Logit Adjustment
python train_classifier.py --train-index generated/train_index.csv `
  --cv-manifest generated/internal_cv_duplicate_near_4fold.csv --fold 0 `
  --model convnext_tiny --image-size 384 --epochs 3 `
  --label-smoothing 0 --logit-adjustment 0

# 目标强权重：本机注册表不列出时使用 hf-hub 前缀，先做加载验收
python train_classifier.py --train-index generated/train_index.csv `
  --cv-manifest generated/internal_cv_duplicate_near_4fold.csv --fold 0 `
  --model "hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384" `
  --image-size 384 --epochs 3 --label-smoothing 0 --logit-adjustment 0

# 清洗前后保持同一配置对照
python train_classifier.py --label-version raw_v1 ...
python train_classifier.py --label-version reviewed_v1 ...
```

## 2026-08-04 并行审计与推理进展

- [x] 四个 Last-stage `best.pt` 已复制到两份独立资产目录，并完成 SHA-256 一致性校验。
- [x] 保存每折 `best_metrics.json`、`run_config.json`、Global OOF、Manifest SHA、环境信息和当前 Git commit；工作树仍为 dirty，未创建容易误导的 Git tag。
- [x] OOF 错误审计完成：1,139 条中 1,121 正确、18 错误；`乱建` 4 张和 `正常` 7 张全部漏检；非漂浮物误判为漂浮物 13 张。
- [x] 生成 `runs/repair_v2/global_oof/analysis/`：六类指标、少数类错误清单、低置信样本、小 margin 样本和高置信错误清单。
- [x] 场景泄漏审计完成：dHash≤2 的近重复组件未跨 Fold，但 `file_block_0005` 存在大量跨 Fold 同块风险；已发现 `02150.jpg` 与测试图 `02151.jpg` 的相邻帧/固定背景候选，当前成绩不能称严格 Group-OOD。
- [x] 新增 `infer_ensemble.py`：四个 Last-stage Checkpoint 等权平均 Softmax 概率，支持 695 张测试集推理和 Dry-run 校验。
- [x] 完成真实 GPU 推理冒烟：输出 695 条、文件名无重复/遗漏，使用显式或默认 Manifest 校验均通过；当前输出仅为 `submission_dryrun_raw_v1.json`，不是最终提交。
- [x] 修复 `validate_submission.py` 的默认 Manifest 路径，使其从项目目录运行时不再重复拼接 `competition/shuzhi_anomaly`。
- [x] 打包 11 张少数类人工复核包，包含原图、官方标签/模型预测参考、复核模板、验证方法、图片 SHA-256 和 CSV 校验脚本。
- [x] 完成 11 张人工复核统一口径：仅 `00033.jpg: 正常→有漂浮物`、`02111.jpg: 正常→乱堆` 改标，其余 9 张保留官方标签；严格校验通过，`relabel=2`。
- [x] 生成 `generated/train_reviewed_v2.json` 和 `generated/reviewed_label_audit_v2.json`；原始 `train.json`、`raw_v1`、`reviewed_v1` 未修改。
- [x] 使用现有 OOF 重新计算 reviewed_v2 指标：Weighted F1 `0.982022`、mIoU `0.636632`；不重新训练。

当前状态：11 张少数类已完成统一人工复核，仅 2 张明确改标；`reviewed_v2` 和现有 OOF 重算已完成。模型主线仍冻结，不启动新的四折训练；下一步保留当前四折 Argmax 测试推理作为第一提交候选，同时记录工程 OOF 的固定背景泄漏风险。
