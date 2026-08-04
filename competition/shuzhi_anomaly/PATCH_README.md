# 赛题三分类训练修复包 v2

## 覆盖范围

把本压缩包中的以下文件复制到：

```text
competition/shuzhi_anomaly/
```

- `classification_common.py`：共享模型、数据、预处理、指标工具。
- `train_classifier.py`：替换原训练脚本。
- `extract_frozen_features.py`：冻结特征 + Logistic Regression OOF。
- `aggregate_oof.py`：拼接四折最佳 OOF，计算唯一的全量 OOF 指标。
- `crossfit_majority_threshold.py`：在其他折调阈值、在留出折验证，避免直接在同一 OOF 上乐观调参。
- `run_repair_round.ps1`：单折“只训 Head → 解冻最后 Stage”命令模板。

复制前建议备份原 `train_classifier.py`。本包不会修改原图、`train.json`、Manifest 或已有 `runs/`。

## 这次修了什么

1. `convnext_tiny_384` 自动解析为：
   `hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384`。
2. 纯 CE 默认 `label_smoothing=0`。
3. 支持 `head / last_stage / last2_stages / full` 分层解冻。
4. 支持 Backbone/Head 差分学习率。
5. 支持 CUDA AMP、梯度裁剪、Early Stopping。
6. 最佳 Epoch 保存每张验证图的六类 Logits 和概率。
7. JPG/JPEG/PNG 全格式发现；EXIF 转正；模型配置对应的插值、mean/std；保持全图 resize+padding。
8. 原 `class_sequence` 作为 legacy 参数会明确报错，防止再次每轮只训练 6～24 张图。
9. 新增温和 `power_balanced`：`count^(-alpha)`，默认 alpha=0.25；第一轮仍建议 `standard`。
10. 支持可选 Balanced Softmax，但排在干净 CE/cRT 后测试。

## 安装

在现有 PyTorch/CUDA 环境内，仅补缺失模块：

```powershell
pip install -r requirements_patch.txt
```

不要为了安装本包重装 PyTorch。

## 第一轮建议命令

### A. 冻结特征筛选

```powershell
python extract_frozen_features.py `
  --source-root "D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集" `
  --train-index generated/train_index.csv `
  --cv-manifest generated/internal_cv_duplicate_near_4fold.csv `
  --model convnext_tiny_384 `
  --out-dir runs/features_convnext_384_none `
  --class-weight none
```

再跑温和权重：

```powershell
python extract_frozen_features.py `
  --source-root "D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集" `
  --train-index generated/train_index.csv `
  --cv-manifest generated/internal_cv_duplicate_near_4fold.csv `
  --model convnext_tiny_384 `
  --out-dir runs/features_convnext_384_power025 `
  --class-weight power --power-alpha 0.25
```

### B. 单折分层迁移

```powershell
.\run_repair_round.ps1 `
  -SourceRoot "D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集" `
  -ProjectDir "." `
  -Fold 0
```

在仓库根目录运行时，`ProjectDir` 改为：

```powershell
-ProjectDir "competition/shuzhi_anomaly"
```

### C. 四折完成后汇总

```powershell
python aggregate_oof.py `
  runs/repair_v2/fold0_last_stage `
  runs/repair_v2/fold1_last_stage `
  runs/repair_v2/fold2_last_stage `
  runs/repair_v2/fold3_last_stage `
  --out-dir runs/repair_v2/global_oof `
  --expected-count 1139
```

### D. 交叉拟合“有漂浮物”阈值

```powershell
python crossfit_majority_threshold.py `
  runs/repair_v2/global_oof/combined_oof_predictions.csv `
  --out-dir runs/repair_v2/crossfit_threshold
```

## 推荐实验顺序

1. `extract_frozen_features.py`：ConvNeXt none / power 0.25。
2. Fold 0：Head-only。
3. Fold 0：Last-stage。
4. Fold 0 明显超过 B0 后再扩四折。
5. 拼接 Global OOF。
6. 交叉拟合多数类阈值。
7. 再测试 cRT、局部 2×2、EfficientNetV2。

## 兼容说明

- `hf-hub:` 加载需要网络或本地 Hugging Face 缓存。首次下载后可离线复用。
- 如果比赛机完全离线，先在联网机器下载权重缓存，再复制 `weights/timm` 或 Hugging Face cache。
- 本包无法在此环境执行真实 GPU 训练，因为没有你的图像目录和 CUDA 设备；已做静态编译与轻量单元测试。
