# 山水智鉴六分类：公众号论文与可迁移方案筛选

本报告只服务于 `competition/shuzhi_anomaly` 的单张 RGB 六分类任务：

```text
图片 → 乱采 / 乱建 / 乱堆 / 乱占 / 有漂浮物 / 正常
```

官方评分是加权 F1（weighted F1），不是 mIoU；mIoU、Macro-F1 和每类 F1 用于诊断长尾类别是否失效。本任务不是像素级分割，科大讯飞水体分割项目不属于本报告的主任务。

## 结论先行

最值得直接落地的顺序是：

1. 保留普通采样作为基线，再测试 Balanced Softmax 或现有 Logit Adjustment；不要把强类别均衡采样和类别修正损失同时拉满。
2. 在同一内部 4-fold 上比较 `resnet18`、`convnext_tiny`、`swin_tiny_patch4_window7_224` 的 ImageNet 预训练权重。
3. 只有当图片确实以鸟瞰/遥感视角为主，再测试 RSP 的 ResNet-50 或 Swin-T 权重。
4. 暂不采用 BCL、GeRSP、DINOv2/SigLIP 作为第一轮方案；它们要么训练成本高，要么输入/模型适配复杂，不能证明会提高当前 weighted F1。

## YOLO-CLS 与 timm 选型

两者都能完成“整图输出一个类别”，但当前主线选 `timm`：

| 维度 | YOLO-CLS | timm 分类适配器 |
|---|---|---|
| 任务匹配 | 可以做整图分类 | 直接匹配当前六分类 |
| 当前标签接入 | 通常需要整理成分类目录/配置 | 可直接读取现有 JSON、Manifest |
| 官方默认验证 | 以 Top-1/Top-5 为主 | 可按 weighted F1 选最优模型 |
| 长尾处理 | 需要自定义 Trainer/Loss | 现有脚本可直接加 Logit Adjustment/Balanced Softmax |
| 连续帧与 Group Fold | 需要改数据管线 | 已支持 `sequence_id`、内部折和采样消融 |
| 整图保留 | 默认裁剪可能丢掉岸边异常 | 当前使用 resize + padding，便于保留全景 |

YOLO-CLS只保留为低成本对照实验，不作为第一主线；YOLO Detection 不进入本任务，因为没有框标注，也不要求输出目标位置。官方 YOLO 分类文档明确分类输出单个类别和置信度，但默认训练/验证使用裁剪变换；官方文档也提供自定义分类数据集和 Trainer 的方式。当前项目已经有更贴合比赛评分和数据隔离要求的 `timm` 入口，因此没有必要为 YOLO 重新搭一套训练管线。

## 候选筛选

| 优先级 | 微信文章 | 可迁移内容 | 当前判断 |
|---|---|---|---|
| P0 | [Balanced-Meta Softmax：长尾视觉识别方案解读](20201125_Balanced-Meta%20Softmax_%20长尾视觉识别方案解读/原文.md) | Balanced Softmax、Meta Sampler、过平衡分析 | 最契合。先移植 Balanced Softmax，不移植 Meta Sampler |
| P1 | [timm 图像分类模型选择指南](20260313_timm%20图像分类模型选择指南/原文.md) | 直接加载预训练分类基座、按规模选模型 | 最容易形成可复现实验 |
| P1 | [Kaggle知识点：timm预训练模型](20210406_Kaggle知识点：timm预训练模型/原文.md) | `timm.create_model(..., pretrained=True)`、模型枚举和特征提取 | 可直接套用到当前训练入口 |
| P1 | [解锁图像识别新境界：深入探索TIMM](20240104_解锁图像识别新境界：深入探索PyTorch%20Image%20Models（TIMM）/原文.md) | 预训练、迁移学习、增强和评估流程 | 支持主线选 timm，但不提供比赛特定权重 |
| P1 | [使用SwinTransformer进行图片分类](20230613_使用SwinTransformer进行图片分类/原文.md) | timm Swin 分类代码和预训练加载方式 | 可做 Swin-T 基线；文章本身不是长尾实验 |
| P1 | [RSP：遥感预训练的实证研究](20220511_RSP：遥感预训练的实证研究/原文.md) | RSP-ResNet-50、RSP-Swin-T、RSP-ViTAEv2-S 权重 | 有迁移价值，但视角域差异可能抵消收益 |
| P2 | [图像分类训练技巧之数据增强总结](20230817_图像分类训练技巧之数据增强总结/原文.md) | RandAugment、Mixup、CutMix、Random Erasing | 先不加；小样本异常类别容易被混合标签污染 |
| P2 | [基于PyTorch的小样本学习，图像分类](20231005_基于PyTorch的小样本学习，图像分类/原文.md) | Few-shot、原型/匹配网络、CLIP 零样本思路 | 解释少数类困难，但不作为第一轮训练框架 |
| P2 | [高分影像场景分类的半监督深度卷积神经网络学习方法](20210914_测绘学报%20_%20杨秋莲：高分影像场景分类的半监督深度卷积神经网络学习方法/原文.md) | 高置信伪标签、自学习、遥感场景分类 | 仅作后续研究；不能直接把官方无标签测试集当训练标签 |
| P2 | [ResNet 的性能不够好？](20230212_ResNet%20的性能不够好？ResNet%20听了直摇头并强势反击：是你的训练策略不行吧！/原文.md) | timm 训练策略、种子稳定性、预训练权重 | 吸收训练思想，不照搬 ImageNet 600 epoch 配置 |
| P3 | [CVPR2022：计算机视觉中长尾数据平衡对比学习](20220724_CVPR2022：计算机视觉中长尾数据平衡对比学习/原文.md) | BCL 表征学习、类补充和类平均 | 论文有价值，但官方实现按 4 GPU/大 batch 设计，不适合第一轮 |
| P3 | [GeRSP 通用知识增强遥感预训练](20240111_遥感论文%20_%20Arxiv%20_%20GeRSP：一种新颖的通用知识增强遥感预训练框架，用于场景分类、目标检测、语义分割等下游任务！/原文.md) | ImageNet + MillionAID 两阶段预训练 | 需要外部大数据和预训练流程，暂不采用 |
| P2 | [科技护河：天梭智飞水域巡检应用](20260311_低空应用专题：科技护河：天梭智飞在水域巡检中的应用/原文.md) | 业务语义与“四乱/漂浮物”对应关系 | 可用于理解类别和应用，不提供可复用模型权重 |

## 最值得复用的方案

### 1. Balanced Softmax：优先移植损失，不照搬强均衡采样

官方实现的核心是：

```python
loss = cross_entropy(logits + log(samples_per_class), labels)
```

它有助于降低模型只预测“有漂浮物”的倾向，但不保证 weighted F1 上升：weighted F1 会按验证集真实类别数量加权，少数类提升必须抵消由此带来的多数类 FP 才算有效。

但是论文同时指出，Balanced Softmax 与强类别均衡采样叠加会出现“过平衡”。这与当前数据最少类只有4张、旧 `class_sequence` 采样器会压缩 epoch 的问题直接相关。

推荐实验顺序：

```text
E0 standard sampler + CE
E1 standard sampler + Balanced Softmax
E2 natural-distribution encoder + frozen classifier head + balanced classifier training
E3 standard sampler + Logit Adjustment
```

不要一开始同时使用 class-balanced sampler、类别权重、Focal、Balanced Softmax 和强 Label Smoothing。

### 2. timm 基座：先选小模型，不直接上 Swin-Base

当前环境能够识别这些模型族：

```text
resnet18
resnet50
convnext_tiny
swin_tiny_patch4_window7_224
swin_base_patch4_window7_224
vit_base_patch14_dinov2
vit_base_patch16_siglip_224
```

第一轮建议：

- `resnet18`：低成本 sanity baseline；
- `convnext_tiny`：小数据、强卷积归纳偏置，作为主力候选；
- `swin_tiny_patch4_window7_224`：测试全局上下文建模；
- `swin_base_patch4_window7_224`：暂不作为第一轮，参数量和过拟合风险更高。

注意：Swin-T/Base 的预训练配置是固定 224 输入，使用时应传 `--image-size 224`；当前整图 padding 的 384 方案优先给 ResNet/ConvNeXt 使用。

### 3. RSP 权重：作为遥感域消融，不作为默认答案

官方 RSP 仓库公开了：

- RSP-ResNet-50-E300；
- RSP-Swin-T-E300；
- RSP-ViTAEv2-S-E100。

这些权重来自 MillionAID 鸟瞰遥感场景。如果当前比赛图片主要是岸边/水面现场视角，RSP 与测试域不一定匹配。因此只做一个对照：

```text
ImageNet ConvNeXt/Swin → RSP-Swin-T 或 RSP-ResNet-50
```

只比较内部 Group/近重复约束折上的 weighted F1，并同时看 mIoU 和每类 F1；不根据论文中的遥感分类 Accuracy 直接推断本赛题收益。RSP checkpoint 需要按官方说明提取 backbone 权重，不能直接当作 timm `pretrained=True` 使用。

## 不建议现在套用的内容

- BCL：官方实现面向 ImageNet-LT/iNaturalist，使用大 batch 和4 GPU；当前少数类样本太少，先做长尾损失更稳妥。
- GeRSP：需要 MillionAID 和 ImageNet 两阶段预训练，超出“只用现有数据”的范围。
- DINOv2/SigLIP：可以作为冻结特征/零样本研究，但模型和输入配置较重，不能替代当前 weighted-F1 基线。
- Mixup/CutMix：异常类别具有场景语义，随机拼接可能制造错误监督；等 CE/Balanced Softmax 基线稳定后再单独消融。
- 水域巡检应用文章：适合确认“四乱”和漂浮物的业务语义，不等于公开了可用分类模型。

## 最终落地清单

```text
P0 复核118张少数类 + 固定内部折 + standard sampler
P1 resnet18 / convnext_tiny + CE
P1 Balanced Softmax（自然采样）
P1 Swin-T 224输入 + CE
P2 RSP-Swin-T 或 RSP-ResNet-50 消融
P2 RandAugment / Mixup / CutMix 单独消融
P3 BCL、GeRSP、DINOv2/SigLIP
```

所有选择以官方 weighted F1 为准，同时看六类 mIoU、每类 F1、FP、FN 和预测分布；公众号或论文中的 Accuracy、分割 mIoU、检测 mAP 不直接作为本赛题成绩。

## 官方代码与论文入口

- Balanced Meta-Softmax 分类实现：<https://github.com/jiawei-ren/BalancedMetaSoftmax-Classification>
- Balanced Contrastive Learning：<https://github.com/FlamieZhu/Balanced-Contrastive-Learning>
- RSP 官方仓库：<https://github.com/ViTAE-Transformer/RSP>
- timm 官方仓库：<https://github.com/huggingface/pytorch-image-models>
- ResNet strikes back：<https://arxiv.org/abs/2110.00476>
- GeRSP 论文：<https://arxiv.org/abs/2401.04614>
