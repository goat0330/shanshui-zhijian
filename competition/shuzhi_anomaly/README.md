# 赛题3 水域综合异常识别｜初赛算法说明

## 任务边界

初赛是严重长尾的六分类单张图片识别：

```text
一张 JPG/PNG 图片 → 一个类别 → 一个 label
```

不包含像素级 Mask、目标框、视频轨迹、经纬度或遥感多时相输入。产品方案可以接入视频、无人机和遥感，但这些能力不进入本次初赛主模型。

## 数据事实

- 本机完整数据：`D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集\`。
- 训练集 1144 张，全部可解码；当前测试目录为 691 张 JPG + 4 张 PNG，共 695 张，全部可解码。旧脚本只扫描 JPG，已修正为扫描 JPG/PNG/JPEG。
- 训练标签来自 `train.json`；测试集无标签。
- 当前扫描发现全量 9 组、18 张精确重复文件；测试清单不再混用 691 和 695 两个版本。
- `train.json` 与实际图片解码尺寸有 4 条不一致：`02486–02489.jpg`。训练读取实际解码尺寸，官方元数据不自行改写。

| 类别 | 数量 | 占比 |
|---|---:|---:|
| 有漂浮物 | 1026 | 89.7% |
| 乱占 | 60 | 5.2% |
| 乱采 | 24 | 2.1% |
| 乱堆 | 23 | 2.0% |
| 正常 | 7 | 0.6% |
| 乱建 | 4 | 0.3% |

文件编号、排序位置、类别目录名和原始目录顺序禁止作为模型输入特征。

## 前期处理入口

前期工作不占用 GPU，入口和产物见 [PREPROCESS_TODO.md](PREPROCESS_TODO.md)：

```powershell
python prepare_data_manifest.py
```

该脚本只做 CPU 数据清单、图片解码/尺寸检查、SHA-256、dHash 近重复候选、非破坏性训练索引、少数类复核队列、冻结测试清单和临时 `sequence_id`。临时 `sequence_id` 仅由文件名连续性推断，必须在取得真实视频来源或人工确认后才能用于最终 Group Fold。

当前工作区尚未发现带标签的独立 `val` 记录；无标签测试集不能用于验证。先运行 `build_internal_cv.py` 从 1,139 张启用训练图片中生成内部折，训练脚本支持用 `--cv-manifest + --fold` 逐折验证；这不改变测试集隔离原则。

## 验证与报告

当前先建立一个可执行的内部验证口径；待真实视频/场景来源可确认后，再增加严格 Group-OOD 口径：

- `Competition-IID Val`：exact/near 重复组件不跨折的内部 4-fold；
- `Group-OOD Val`：同一场景、相机、连续序列和近重复图片只能进入同一 Split，目前需要真实来源组或人工确认，不能拿临时文件名块冒充。

评分文件已确认：赛题三按加权 F1（weighted F1）评分，每张图片只输出一个 `label`，不需要目标框或位置。内部模型选择默认以 weighted F1 为准，同时输出六类混淆矩阵 mIoU、Macro-F1、Balanced Accuracy、每类 Precision/Recall/F1 和预测分布，防止加权指标掩盖少数类失效。

当前无训练常数基线 B0（全部预测“有漂浮物”）在内部折上的 Weighted F1 约为 0.842～0.857；任何正式模型必须在同一折分和指标实现下超过该基线。

将四折验证预测拼接后的 B0 全量 OOF Weighted F1 为 `0.847430`。P0 的 `reviewed_v1` 当前只透传官方 `train.json` 标签，改标数量为 0；这不是已经完成视觉人工改标，而是保留官方标签的可追溯版本。

当前本机 `timm 1.0.28` 可识别 `convnext_tiny` 和 `efficientnetv2_rw_s`；具体带后缀的模型 ID 必须先通过本机 `timm.list_models()` 验证，不能直接照抄外部配置名。

训练脚本支持 `--label-version raw_v1|reviewed_v1`；当前两者标签一致，后续若有明确人工改标，可用同一配置进行清洗前后对照。

当前折分审计结果：精确重复跨折 0，近重复跨折 0；临时文件名序列仍有跨折，因此严格 Group-OOD 尚未就绪。

CPU 产物还包括：`generated/train_manifest_v1.csv`、`generated/test_691_vs_695_diff.csv`、`generated/constant_baselines_duplicate_near_4fold.csv`、`generated/cv_audit_duplicate_near_4fold.json` 和 `config/label_map.json`。

## 最小流程

```text
数据审计 → 少数类/标签复核 → 内部折分 → 六分类模型 → weighted F1 + 混淆矩阵诊断 → Bad Case → Exporter
```

内部提交包结构：

```text
自定义名称.tar.gz
├── code/
├── design/
└── result/result.json
```

在官方 `result.json` 示例明确前，Exporter 读取测试集官方元数据，保留 `filename / width / height` 及原顺序，只填写 `label`；最终以官方示例为准。

## 与水体分割的关系

科大讯飞水体分割属于独立项目；现有分割脚本不作为本分类前处理入口，也不在本项目中移动或删除。赛题三只输出单个 label，不接入目标检测框、分割 Mask 或位置预测。
