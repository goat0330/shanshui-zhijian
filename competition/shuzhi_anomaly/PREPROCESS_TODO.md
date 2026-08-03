# 水域六分类：前期处理清单

目标：只使用现有数据，先完成数据和标签整理，再训练分类模型；不修改源图片，不把无标签测试集当验证集。

## 已完成（CPU，不占 GPU）

- [x] 读取 `train.json`，核对六类标签和图片是否一一对应。
- [x] 检查 JPG 是否可解码、实际尺寸和官方尺寸是否一致。
- [x] 计算 SHA-256，发现精确重复图片并生成非破坏性训练索引。
- [x] 计算 CPU-only dHash，生成相邻文件编号的近重复候选；候选只供复核，不自动删除。
- [x] 生成临时 `sequence_id`。当前仅由连续文件编号推断，置信度为 low，不能当作最终 Group Fold 依据。
- [x] 生成少数类、尺寸异常、重复帧和近重复帧复核队列。
- [x] 生成类别统计、训练索引和审计报告。
- [x] 生成冻结的无标签测试集清单 `test_manifest_v1.csv` 及 SHA-256。
- [x] 将人工复核字段、优先级和原始标签写入复核队列；不覆盖 `train.json`。

当前这一路径的扫描结果：

```text
有标签图片       1144
无标签图片       691
图片解码失败     0
尺寸不一致       4
精确重复组       9（18 张）
训练索引启用     1139
近重复候选       169 对
标签复核候选     241 张
临时序列块       9
可计算验证 mIoU  否，当前没有带标签 val 记录
```

历史清理记录曾对另一份/另一时点数据报出 695 张无标签图；最终训练前必须重新扫描实际数据根目录并固定一份清单，不能混用 691 和 695 的旧统计。

## 待完成（仍以 CPU 为主）

- [ ] 先人工确认复核队列前 118 个少数类样本；只修改明确错误标签，不确定样本保留 `uncertain`。
- [ ] 如果能取得原始视频/文件夹信息，用真实来源替换临时 `sequence_id`；目前的文件名连续块只能做候选分组。
- [ ] 运行 `build_internal_cv.py`，先得到 exact/near 去重约束的内部 4-fold；真实来源组确认后再做最终 Group Fold。
- [ ] 训练默认使用 `standard` sampler；`class_sequence` 暂时只做消融，不能作为默认方案。当前最少类只有 4 张，旧实现会把每个 epoch 压缩到约 24 张，丢弃绝大多数训练数据。
- [ ] 先跑自然分布 + CE 基线，再比较冻结分类头/Logit Adjustment；不要同时叠加强采样、类别权重、Focal 和强 Logit Adjustment。
- [ ] 训练输入默认改为保持全景的 resize + padding，避免 `224 CenterCrop` 裁掉小异常；局部 2×2 视图留到基线之后。
- [ ] 用六类混淆矩阵计算 mIoU，并同时保存 Accuracy、Macro-F1、Balanced Accuracy、每类 Precision/Recall/F1、预测分布和错误样本。
- [ ] OOF 预测稳定后，再考虑预训练特征近邻和 Cleanlab 排序；这不是当前必须下载和运行的前置步骤。

## 产物

- `generated/data_manifest.csv`：全量文件、标签、尺寸、哈希和临时序列。
- `generated/train_index.csv`：不删除源数据的训练使用索引。
- `generated/exact_duplicate_groups.csv`：精确重复组。
- `generated/near_duplicate_candidates.csv`：相邻编号近重复候选。
- `generated/label_review_candidates.csv`：少数类和异常样本复核队列。
- `generated/exact_duplicate_override.json`：仅在出现训练/测试精确重复时保留待确认处置，不自动改测试标签。
- `generated/test_manifest_v1.csv`：当前无标签测试集冻结清单。
- `generated/internal_cv_duplicate_near_4fold.csv`：内部 CV 折分配；不等同于最终视觉序列 Group Fold。
- `generated/sequence_review_summary.csv`：临时序列块摘要。
- `generated/audit_report.json`：机器审计结果。
- `prepare_data_manifest.py`：CPU 前处理入口。
- `train_classifier.py`：后续 timm 分类训练入口，不负责前期清洗。

训练时如需启用非破坏性精确去重索引，显式传入：

```powershell
python train_classifier.py --train-index generated/train_index.csv --val-json <带标签验证集.json>
```

没有官方带标签 val 时，用内部折训练/验证一个 fold：

```powershell
python build_internal_cv.py
python train_classifier.py --train-index generated/train_index.csv `
  --cv-manifest generated/internal_cv_duplicate_near_4fold.csv --fold 0
```

## CPU/GPU 资源安排

| 工作 | CPU | GPU |
|---|---:|---:|
| JSON、Manifest、标签统计 | 需要 | 不需要 |
| 图片解码、尺寸检查、SHA-256、dHash | 需要 | 不需要 |
| 重复/近重复候选生成 | 需要 | 不需要 |
| 标签复核和索引整理 | 需要 | 不需要 |
| 内部折分配、复核、指标准备 | 需要 | 不需要 |
| 分类模型训练 | 可运行但较慢 | 推荐，后续再占用 |
| 科大讯飞水体分割训练 | 不建议 | 继续优先占用 |

本阶段只做 CPU 前处理和内部折准备，不启动 GPU 训练；分类训练时再错峰使用 GPU，科大讯飞水体分割继续优先占用 GPU。
