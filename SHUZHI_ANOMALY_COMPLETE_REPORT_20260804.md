# 赛题三水域综合异常识别当前成果汇总报告

更新时间：2026-08-04  
项目：山水智鉴/赛题三——水域综合异常识别  
当前交付分支：`feat/platform-inference-v1`<br>
推理包代码提交：`b0243f3b24fca3edb5843befa8804e8ad21b342f`<br>
OpenChamber 完成事件：`shuzhi-overnight-20260804`，状态 `completed`，canonical artifact 检查通过。<br>
汇总报告提交：以本分支最新 HEAD 为准。

## 一、结论先行

本轮已经把赛题三从“本地训练结果”整理为“可交给比赛平台执行的正式离线推理包”。正式包采用 `.tar.gz` 形式，包含四个 reviewed_v2 四折模型权重；另提供一个不含权重和图片、大小远低于 30 MB 的核心代码包，用于代码审查、版本交接和后续重新打包。

当前推荐使用 reviewed_v2 四折候选提交。其 Global OOF 结果为：

| 指标 | raw_v1 冠军主线 | reviewed_v2 续训候选 | 变化 |
|---|---:|---:|---:|
| Weighted F1 | 0.979403 | **0.982875** | +0.003472 |
| mIoU | 0.629527 | **0.639108** | +0.009582 |
| Macro-F1 | 0.647091 | **0.652262** | +0.005171 |
| Accuracy | 0.984197 | **0.986831** | +0.002634 |
| 错误数 | 18 | **15** | -3 |
| 有漂浮物 Recall | 0.998041 | **0.999022** | +0.000980 |

这一结果通过了预设候选门槛：`0.982875 >= 0.979403`。冠军 `repair_v2` 原始权重没有覆盖，仍保留为候选 A；reviewed_v2 作为候选 B 完成测试推理和正式离线包构建。

### OpenChamber 本轮完成态

本轮 CUDA 训练和后续诊断已由 OpenChamber session `ses_037229559ffeXuWP1YVcFSn0Br` 完成。通过 supervisor 的 canonical `event-read` 复核：`status=completed`、`artifacts_ok=true`、`ready_for_next_task=true`。四项关键产物位于 `competition/shuzhi_anomaly/runs/overnight_20260804/`，包括四折 checkpoint、Global OOF gate、695 条候选 JSON 和最终报告。完整吸收记录见 `OPENCHAMBER_COMPLETION_ABSORPTION_20260804.md`。

## 二、项目边界和比赛契约

这不是科大讯飞遥感水体分割任务，也不是目标检测任务。赛题三是整图六分类：每张图片只输出一个类别，不输出目标位置、不输出框、不输出分割掩膜。

官方/当前交接输出对象为 JSON 数组，每张图片一条记录，字段和值均为字符串：

```json
{
    "filename": "00000.jpg",
    "width": "4080",
    "height": "3060",
    "label": "有漂浮物"
}
```

固定六类及顺序为：

```text
乱采、乱建、乱堆、乱占、有漂浮物、正常
```

评分材料确认任务为分类任务，核心评分为加权 F1。mIoU、Macro-F1、每类召回率和混淆矩阵用于本地诊断，不能把测试集无标签结果当成真实验证分数。

本项目与其他水体分割/产品化遥感项目保持独立：本轮没有引入分割 mask、YOLO 检测框、外部数据、测试集伪标签或多模态模型。

## 三、数据审计和前期整理

### 3.1 当前数据规模

审计结果：

- 图片总数：1839；
- 有标签训练记录：1144；
- 无标签测试图片：695；
- 测试图片格式：691 张 JPG + 4 张 PNG；
- 标签图片缺失：0；
- 图片解码错误：0；
- 训练索引实际启用记录：1139；
- 原始训练集和测试集没有跨 split 的完全重复组。

原始 `train.json` 标签分布：

| 类别 | 数量 |
|---|---:|
| 有漂浮物 | 1026 |
| 乱占 | 60 |
| 乱采 | 24 |
| 乱堆 | 23 |
| 正常 | 7 |
| 乱建 | 4 |
| 合计 | 1144 |

主要数据风险：

- 完全重复组 9 组、涉及 18 条记录；
- 近重复候选 169 对、近重复组 82 组；
- 4 张尺寸元数据不一致；
- 训练集严重长尾，有漂浮物占绝大多数，正常和乱建极少；
- 现有 `sequence_id` 只能依据连续文件块临时推断，置信度低，尚未等同于真实视频序列。

### 3.2 P0 序列/Group Fold 原则

已经建立了 provisional `sequence_id` 和重复/近重复审计框架。它的作用是防止连续帧或固定背景同时进入训练和验证，避免本地分数虚高。

当前 `file_block_0005` 严格 holdout 结果显示：holdout 共 801 张，其中 800 张是有漂浮物、1 张是正常；如果直接用该块作为验证集，常数预测有漂浮物就能达到 0.9988 accuracy。因此该 holdout 只用于泄漏/风险诊断，不能作为主验证集或训练选模依据。

结论是：Group Fold 方向正确，但当前文件名连续块不是最终真实视频分组；没有原始视频元数据或人工场景确认时，必须把它标记为低置信诊断结果。

### 3.3 人工复核和 reviewed_v2

对 11 张少数类/高风险混淆样本完成了人工统一口径复核：

- 保留官方标签：9 张；
- 明确改标：2 张；
- 不确定样本：0 张；
- 原始 `train.json` 未修改。

两张改标为：

| 文件 | 原标签 | reviewed_v2 | 复核依据 |
|---|---|---|---|
| `00033.jpg` | 正常 | 有漂浮物 | 桥墩附近水面有明显蓝色桶状/容器状人工漂浮物，并带黑色绳管 |
| `02111.jpg` | 正常 | 乱堆 | 岸线右下存在板材、建材和杂物露天成堆；业务合法性不确定，但视觉标签更接近乱堆 |

其余重点样本统一保留：

- `02486–02489.jpg`：保留乱建；不能因为构筑物位于水面平台或出现施工机械就改成漂浮物/乱采；
- `00064.jpg`：正常，仅有道路、车辆和机械不足以判定乱采；
- `00096.jpg`、`00100.jpg`：正常，垃圾已经收集在清漂船内，不是水面散布漂浮物；
- `00114.jpg`：正常，规范化滨水步道和护岸；
- `01086.jpg`：正常，正常取水口/水工设施。

`train_reviewed_v2.json` 是由人工决策生成的派生标签文件；官方原始文件、raw_v1 和 reviewed_v1 保持不动。

## 四、训练和模型选择

### 4.1 训练配置

正式候选模型采用 ConvNeXt-Tiny 384 分类模型：

- timm 架构：`convnext_tiny`；
- 原始训练配置别名：`convnext_tiny_384`；
- 384 输入；
- `last_stage` 分层解冻；
- backbone 学习率 `5e-6`；
- 分类头学习率 `5e-5`；
- weight decay `0.05`；
- label smoothing `0`；
- logit adjustment `0`；
- standard sampler；
- 最多 10 epoch，early stopping patience 3；
- batch size 16；AMP；gradient clip 1；seed 42；
- 以 Weighted F1 选择 best checkpoint。

本轮训练由 CUDA 单进程顺序执行，CPU worker 负责 OOF 重算、场景 holdout 和错误转移分析，没有并发启动两个 CUDA 训练进程。

运行环境：

- GPU：NVIDIA GeForce RTX 2070 with Max-Q Design，8 GB；
- Python：3.11.5；
- PyTorch：2.6.0+cu118；
- timm：1.0.28；
- 峰值温度约 56°C；
- 四个原始冠军 checkpoint 的 SHA256 在训练前后保持一致。

### 4.2 四折续训结果

每个 reviewed_v2 fold 都从对应 repair_v2 冠军 best.pt 初始化，未覆盖原 checkpoint：

| Fold | Weighted F1 | 原冠军 | 错误数 | 结果 |
|---:|---:|---:|---:|---|
| 0 | 0.983987 | 0.983987 | 4 | 与冠军一致 |
| 1 | 0.989647 | 0.989647 | 2 | 与冠军一致 |
| 2 | 0.980900 | 0.970707 | 4 | +0.010193，救回 00033/02111 |
| 3 | 0.976883 | 0.973410 | 5 | +0.003473，解决 00020 |

没有出现 NaN/Inf，四个 checkpoint 均正常写出。

### 4.3 448 分辨率诊断

在包含少量乱建和正常样本的 fold2 上做了 448 分辨率单 fold 诊断：

- Weighted F1：0.984405，对比 384 fold2 的 0.980900；
- 错误数：4 降至 3；
- 解决 `02044.jpg`；
- 结论：满足扩展到四折的条件，但本轮没有把 448 单折诊断直接替换为正式主线。

### 4.4 场景 holdout 诊断

`file_block_0005` holdout：

- holdout：801；
- train：343；
- holdout 类别为 800 张有漂浮物 + 1 张正常；
- Weighted F1：0.996878；
- Macro-F1：0.1664；
- mIoU：0.3321。

该分数被单一类别构成严重抬高，不能证明泛化能力；该实验仅用于识别固定场景/连续帧泄漏风险。

## 五、正式离线推理包的核心改造

原来的推理脚本依赖本地 `test_manifest_v1.csv`，固定 695 条数据，并通过项目路径寻找模型。它适合本地复现，不适合平台把隐藏测试图片直接交给程序执行。

本轮改造的核心代码如下：

### `main.py`

- 新增 `--input-dir` 和 `--output` CLI；
- 动态递归扫描 `.jpg/.jpeg/.png`，后缀大小写不敏感；
- 按 `path.name` 稳定排序；
- 不允许不同目录出现重复 filename；
- 不再固定 695 张，任意数量大于 0 的图片都能运行；
- 保存图片原始宽高，模型输入单独做 EXIF 转正和 RGB 转换；
- 支持 `auto/cpu/cuda`；
- 四折模型按 fold0→fold3 顺序逐个加载和释放；
- 默认只输出四字段 JSON；
- 可选导出概率 CSV，但不是正式提交必需字段；
- 使用临时文件后原子替换输出，避免半写 JSON。

### `inference_common.py`

- 固定离线 `timm.create_model("convnext_tiny", pretrained=False, num_classes=6)`；
- 不导入项目训练代码，不读取项目绝对路径；
- 严格检查 checkpoint 文件存在、SHA256、标签顺序、fold、模型名、freeze mode、输入尺寸、插值、mean/std；
- `strict=True` 加载 state dict，missing/unexpected key 直接失败；
- 复刻训练验证预处理：384 ResizePad、BICUBIC、mean 色填充、ImageNet mean/std；
- 检查 softmax 概率合法性并确保每行和为 1；
- GPU 上只保留当前 fold 模型，完成后 `del`、GC 和 CUDA cache 清理。

### 其他文件

- `model_manifest.json`：标签顺序、架构、输入预处理、四折相对路径和权重 SHA256；
- `validate_runtime.py`：不需要输入图片即可完成依赖、权重哈希和 strict load 自检；
- `requirements.txt`：仅列出 timm、Pillow、PyYAML、huggingface-hub、safetensors，不覆盖平台预装的 Torch/CUDA；本机精确版本另记于 `requirements-full-local.txt`；
- `README.md`：平台调用方式和输出格式；
- `checksums.sha256`：正式包文件校验值。

## 六、正式推理包内容

正式 `.tar.gz` 内恰好包含以下 11 个文件：

```text
shuzhi_platform_inference_v1/
├── main.py
├── inference_common.py
├── model_manifest.json
├── requirements.txt
├── README.md
├── validate_runtime.py
├── checksums.sha256
└── weights/
    ├── fold0_best.pt
    ├── fold1_best.pt
    ├── fold2_best.pt
    └── fold3_best.pt
```

四个正式权重 SHA256：

| Fold | SHA256 |
|---:|---|
| 0 | `d177b6e8af8f37f7129e45df4d636865dcb82bab624b7cfc2aa21d1d2c2d3899` |
| 1 | `704d5c28e5a3b87ddea75e8a51116000124ee4b9e1aa81c4a523038d87564297` |
| 2 | `de9000c830abe3606a4a7f4d2c7575f2cc0745c5a7dd417833f10091daa30664` |
| 3 | `5f32f1ab6bc4cd97f3d72699892d791b88c2346e15767590e6e69514b8ab0c64` |

正式推理运行命令：

```powershell
python path\to\shuzhi_platform_inference_v1\main.py `
  --input-dir path\to\hidden_images `
  --output path\to\submission.json
```

正式包不包含训练集、测试集、train.json、review CSV、OOF、混淆矩阵、旧 submission、test manifest、HF cache、Git 仓库和任何图片。

## 七、验证结果

### 7.1 运行时自检

`validate_runtime.py` 通过：

- 四个 checkpoint SHA256 全部匹配；
- 四个 checkpoint 元数据全部匹配；
- 四个 state dict 均 strict load 通过；
- CUDA 可用，torch/timm/Pillow 版本与锁定版本一致。

### 7.2 动态小样本

构造 11 张独立 sandbox 输入：

- JPG 和 PNG 混合；
- 嵌套目录；
- 横向和纵向图片；
- 多种分辨率；
- CUDA 推理通过；
- CPU 推理通过；
- CPU/CUDA 输出完全一致；
- 11 条记录字段、类型、标签集合和 filename 排序全部通过。

### 7.3 离线隔离

从非项目工作目录执行独立复制的推理包，并设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，同时用 socket 阻断器禁止网络。推理成功，未发生网络访问，也未读取项目外训练缓存。

### 7.4 695 张回归

正式动态入口扫描原始 695 张测试图片，与旧的 `submission_reviewed_v2.json` 逐条比较：

| 检查项 | 结果 |
|---|---:|
| 数量 | 695 vs 695 |
| filename 顺序差异 | 0 |
| width 差异 | 0 |
| height 差异 | 0 |
| label 差异 | 0 |
| 总记录差异 | 0 |
| 状态 | PASS |

当前 695 张候选预测分布为：有漂浮物 529、乱占 126、乱采 33、乱堆 6、乱建 1、正常 0。`正常=0` 和 `乱建=1` 是模型能力风险，已经通过回归证明不是新推理入口造成的。

## 八、交付文件

### 正式平台推理包（含权重）

- 文件：`shuzhi_platform_inference_v1_1.tar.gz`；
- 大小：413,612,492 bytes；
- SHA256：`69851bec9c54892f4961ea8e06380cb8af768ef0ac96bd5d98574dbfcd4cc01a`；
- 校验文件：`shuzhi_platform_inference_v1_1.tar.gz.sha256`。

原 ZIP 仍保留作备用交付，不能与正式 tar.gz 混用时优先使用 tar.gz。

### 核心代码包（不含权重，≤30 MB）

- 文件：`shuzhi_platform_inference_core_v1.tar.gz`；
- 大小：8,621 bytes；
- SHA256：`40831513fdcc464789b9778b69c1522ee47e41bd44150899deae073418ca7311`；
- 校验文件：`shuzhi_platform_inference_core_v1.tar.gz.sha256`；
- 内容：核心 Python、模型 manifest、依赖、README、校验元数据和范围说明；
- 不包含 `.pt` 权重，因此不能单独执行正式推理。

### 审计和结果文件

- `PLATFORM_INFERENCE_AUDIT.md`：正式推理包审计；
- `OPENCHAMBER_COMPLETION_ABSORPTION_20260804.md`：本轮 OpenChamber 完成态和 canonical artifact 吸收记录；
- `platform_695_consistency/consistency_report.json`：695 张逐条一致性摘要；
- `platform_695_consistency/prediction_diff.csv`：空差异表；
- `SHUZHI_ANOMALY_COMPLETE_REPORT_20260804.md`：本汇总报告。

## 九、未做的事情和风险边界

本轮明确没有做：

- 没有重新训练 448 四折正式主线；
- 没有修改原始 `train.json`；
- 没有使用测试集伪标签；
- 没有引入外部数据；
- 没有使用 YOLO 检测框、分割 mask 或多模态模型；
- 没有把 `file_block_0005` holdout 的虚高分当成正式验证分；
- 没有把 448 单折诊断直接替换当前四折候选；
- 没有合并或修改稳定 `main`。

仍然存在的主要风险：

1. 695 张回归是无标签回归，只能说明新入口复现旧候选，不能预测隐藏测试分数。
2. 正常和乱建仍然是极少数类，当前测试候选几乎不输出这两类；若隐藏集含有较多这两类，F1 可能受影响。
3. sequence_id 仍是临时低置信文件块推断，不是原始视频级真实 Group Fold。
4. 平台没有提供完整的 Docker/入口/超时说明，因此正式包提供通用 Python CLI；若平台有自定义包装器，需让包装器调用 `main.py`。
5. 正式 tar.gz 约 394 MB，核心代码包虽小于 30 MB，但不含权重，不能替代正式推理包。

## 十、推荐操作顺序

1. 上传并解压 `shuzhi_platform_inference_v1_1.tar.gz` 作为正式离线推理包。
2. 用 `.sha256` 文件校验上传文件完整性。
3. 在平台环境先执行 `validate_runtime.py`。
4. 用平台给定隐藏图片目录执行 `main.py`，提交生成的四字段 JSON。
5. 不要把核心代码包当成可直接提交的推理包；它仅用于代码审查和轻量交接。
6. 若还有训练时间，后续优先做 448 四折扩展和针对正常/乱建的真实场景补充，而不是继续调推理格式。
