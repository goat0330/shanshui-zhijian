# Head bake-off 448px：普通 OOF 结果

日期：2026-08-07

## 结论范围

本轮已完成四折普通 OOF 的 τ-normalization、LWS 和最小 MARC-style 校准。结果是内部候选筛选，不是平台提交，也不引入 CatAvgMax、外部数据或重新训练 backbone。五场景留出按本轮优先级跳过，未生成 `scene_holdout_metrics.csv`。

## 输入与契约核对

- 当前输入：四个 `shuzhi_platform_inference_v1_2/weights/fold*_best.pt`；训练变换为 448px ResizePad + BICUBIC + ImageNet mean/std。
- 普通 OOF：1139 张，fold 0/1/2/3 = 280/288/288/283。reviewed_v2 中另有 5 张被 `train_index.training_use=False` 排除，未混入。
- pooled feature 与 logits 均由当前 checkpoint 现场提取；没有使用 generic pretrained cache 或旧 `features_448_oof.npz`。模型构建使用 `pretrained=False` 后严格加载当前权重。
- Cross-fit：每个 fold 的校准参数只用该 fold train 的 feature/logits/labels 拟合，该 fold val 只评估并进入 OOF；没有用 val 拟合参数。

## OOF 指标

下表展示 champion、最优几个 τ 候选以及 LWS/MARC；τ=0.0 到 1.0 的完整扫描在 `metrics.csv` 中。

| head | Weighted F1 | mIoU | 乱堆F1 | 乱占F1 | 错误数 | 改变样本 |
|---|---:|---:|---:|---:|---:|---:|
| raw_current | 0.984696 | 0.644923 | 0.978723 | 0.959350 | 13 | 0 |
| tau_0.0 | 0.984696 | 0.644923 | 0.978723 | 0.959350 | 13 | 0 |
| tau_0.1 | 0.984696 | 0.644923 | 0.978723 | 0.959350 | 13 | 0 |
| tau_0.2 | 0.984696 | 0.644923 | 0.978723 | 0.959350 | 13 | 0 |
| lws | 0.984696 | 0.644923 | 0.978723 | 0.959350 | 13 | 0 |
| marc | 0.983812 | 0.642159 | 0.978723 | 0.950820 | 14 | 1 |

当前 checkpoint 现场提取的 raw OOF 与 champion OOF 对齐：最大 logit 绝对差 `8.34e-06`，预测不一致 `0` 张。

### 方法说明

- τ-normalization：仅替换每个 fold 的 `w_c` 为 `w_c / ||w_c||^τ`，保留 pooled feature、backbone 和原始 bias 不变；τ=0.0, 0.1, …, 1.0 全部扫描。
- LWS：保持 fc 每类 weight 方向不变，拟合六个正 scale `s_c`，验证 logits 为 `f · (s_c w_c) + b_c`；使用 CPU/PyTorch LBFGS，并对 `log(s_c)` 加轻微回到 1 的正则。
- MARC-style：对原始 logits 拟合 `a_c z_c + b_c` 的 12 个参数，使用正 scale 参数化和轻微 scale/bias 正则。这是最小 MARC-style 实现，不声称复现论文全部细节。

### H17 Label Over-Smoothing cRT

在冻结 pooled feature 上从当前线性 head 初始化，仅重训分类头；目标类别概率分别设为 `0.55 / 0.65 / 0.75`，其余五类均分剩余概率。三档均低于 champion：

| head | Weighted F1 | mIoU | 乱堆F1 | 乱占F1 | 错误数 | 改变样本 |
|---|---:|---:|---:|---:|---:|---:|
| los_0.55 | 0.983339 | 0.633985 | 0.936170 | 0.967213 | 15 | 8 |
| los_0.65 | 0.983339 | 0.633985 | 0.936170 | 0.967213 | 15 | 8 |
| los_0.75 | 0.982484 | 0.631385 | 0.936170 | 0.959350 | 16 | 9 |

H17 不进入候选，label over-smoothing cRT 路线停止。

## 无标签测试统计

测试集只统计四折平均 softmax 的预测分布与相对 raw champion 的改变样本，不使用任何测试真值，也不据此判断提升。详见 `summary.json` 的 `test_unlabeled_stats`。

| head | 测试样本数 | 相对 raw 改变样本 |
|---|---:|---:|
| raw_current | 695 | 0 |
| lws | 695 | 3 |
| tau_0.1 | 695 | 0 |

## 交付文件

- `head_bakeoff.py`：本轮唯一脚本。
- `metrics.csv`：raw、τ 全扫描、LWS、MARC、H17 三档 cRT 的普通 OOF 指标。
- `oof_deltas.csv`：相对现有 champion 的逐样本改变记录。
- `summary.json`：契约、cross-fit、参数、测试无标签统计和完整指标。
- `RESULT.md`：本报告。

未修改训练脚本、train.json、reviewed labels、模型权重或平台包；未上传、打包或生成 SHA256/lock/audit 产物。
