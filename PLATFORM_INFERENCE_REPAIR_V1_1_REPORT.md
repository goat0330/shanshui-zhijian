# 赛题三平台推理修复 v1.1 验收报告

日期：2026-08-04  
修复包：`D:\\Edge Downloads\\shuzhi-platform-inference-repair-v1.1.zip`  
修复包 SHA256：`94ab8d1c9ff372fce98ab11101d17255a8098d79487c8f933dfb9d9ab1c634c6`

## 1. 应用范围

用户给出的稳定主目录

```text
D:\\研究生作业\\人工智能实践比赛\\shuzhi_platform_inference_v1
```

当前不存在。为避免修改稳定 `main`，实际覆盖的是已存在的独立 worktree：

```text
D:\\研究生作业\\人工智能实践比赛-wt-platform-inference\\shuzhi_platform_inference_v1
```

覆盖前已备份六个原文件和旧校验文件到：

```text
repair_backups\\platform_inference_v1_before_v1_1_20260804_115818
```

v1.1 直接覆盖的六个文件：

```text
main.py
inference_common.py
validate_runtime.py
model_manifest.json
requirements.txt
README.md
```

另外刷新了派生的 `checksums.sha256`，使当前目录的代码校验值与新正式包一致。四个 `.pt` 没有被覆盖。

## 2. 本轮没有改变的内容

- 四个 reviewed_v2 `last_stage` best checkpoint 未改变；
- 四折权重仍为 0.25、0.25、0.25、0.25；
- ConvNeXt-Tiny、384 ResizePad、BICUBIC、ImageNet mean/std 未改变；
- 四折 softmax 概率集成后 argmax 的预测逻辑未改变；
- 六类顺序未改变：乱采、乱建、乱堆、乱占、有漂浮物、正常；
- 输出 JSON 仍只有 `filename/width/height/label` 四个字符串字段；
- 未重新训练、未修改原始标签、未使用测试集伪标签。

因此本轮目标是工程可靠性、平台适配、内存和可验收性提升，不是模型精度提升。695 张标签完全一致已经证明这一点。

## 3. v1.1 的具体提升

### 3.1 运行时自检改为复用正式加载链

旧版 `validate_runtime.py` 单独创建模型并加载 state dict，和正式推理路径存在重复逻辑。v1.1 改为调用正式的 `load_model_for_checkpoint()`，所以自检会实际覆盖：

- checkpoint 文件 SHA256；
- 标签顺序；
- fold 编号；
- `convnext_tiny_384` 模型名；
- `last_stage` freeze mode；
- 384 输入尺寸；
- BICUBIC、mean、std；
- strict state dict 的 missing/unexpected key。

这降低了“自检通过但正式推理加载路径另有问题”的风险。

### 3.2 四折配置由 manifest 驱动

旧版在代码中写死 `range(4)` 和四折列表。v1.1 从 `model_manifest.json` 读取：

- checkpoint 数量；
- fold 顺序；
- 每折相对路径；
- 每折 SHA256；
- 集成权重；
- 集成方法。

当前仍是四折等权，因此预测结果不变；但 manifest 的 fold 数量、权重数量、权重和、顺序不一致时会直接报错。

### 3.3 概率集成改为 running sum

旧版先保存四个 fold 的完整概率矩阵，再统一 `stack().mean()`。v1.1 只保留：

- 当前 fold 的概率矩阵；
- 一份累计概率矩阵。

对于隐藏测试集数量扩大时，累计概率内存从约 `4×N×6` 降为约 `1×N×6`，不会同时保留四折结果。模型仍然按 fold0→fold3 顺序逐个加载和释放。

### 3.4 增加运行性能日志

正式 JSON 不增加任何字段，但标准输出新增：

- 每折耗时；
- 每折权重；
- 总耗时；
- 图片吞吐量；
- batch size、workers、device；
- CUDA 峰值显存。

本机实际记录：

- 11 张 CUDA：总耗时 10.669 秒，1.031 images/s，峰值显存 544.46 MB；
- 695 张 CUDA：总耗时 207.138 秒，3.355 images/s，峰值显存 737.78 MB。

日志只写 stdout，不会污染比赛要求的提交 JSON。

### 3.5 平台依赖策略更安全

v1.0 `requirements.txt` 无条件固定 torch/torchvision，平台如果已有兼容 CUDA 版本，直接安装可能覆盖 CUDA 构建。

v1.1：

- `requirements.txt` 不再固定 torch/torchvision；
- 将完整本机版本放入补丁包的 `requirements-full-local.txt`；
- README 明确要求优先使用平台预装的 torch/torchvision；
- 保留 timm、Pillow 以及 timm 运行所需的 PyYAML、huggingface-hub、safetensors 依赖声明。

这不会改变当前本机推理，但降低平台安装依赖时破坏 CUDA 环境的风险。

### 3.6 路径与 manifest 安全检查更完整

新增/加强了：

- checkpoint 相对路径必须留在包根目录内；
- 拒绝绝对路径和 `..` 穿越；
- 解析后的路径再次检查不能越出包根；
- manifest 的 fold 必须从 0 连续排序；
- 集成权重必须非负、数量匹配并且总和为 1；
- 支持的集成方法必须是明确白名单；
- 输入 filename 冲突时同时报告冲突的完整路径；
- `workers` 参数校验；
- 概率 CSV 禁止空输出。

### 3.7 正式包构建和归档验收工具

补丁包新增三个工具：

- `apply_patch.ps1`：只覆盖六个指定文件，不碰权重；
- `build_platform_package.py`：只把六个运行文件和 manifest 指定的四个权重打入正式包，并重新生成正式包 `checksums.sha256`；
- `verify_release_archive.py`：检查归档路径穿越、符号链接/硬链接/设备文件、重复成员、单一根目录、白名单、多余文件、checksums 和权重 SHA256。

因此正式发布不再依赖人工复制文件清单。

## 4. 实际验收结果

### 4.1 v1.1 修复包自身

- ZIP SHA256：匹配用户提供值；
- Python 静态编译：通过；
- 补丁工具虚拟构建测试：1/1 通过；
- 虚拟正式归档验收：通过。

### 4.2 当前真实权重环境

CPU 和 CUDA 运行时自检均通过：

- Python 3.11.5；
- torch 2.6.0+cu118；
- torchvision 0.21.0+cu118；
- timm 1.0.28；
- Pillow 11.3.0；
- 四个权重 SHA256 全部匹配；
- 四个 strict state dict 全部通过。

### 4.3 小样本前后结果

使用原 11 张混合 JPG/PNG、横竖不同分辨率输入：

- v1.0 CUDA 与 v1.1 CUDA 输出记录数均为 11；
- JSON 逐条完全一致；
- filename 顺序一致；
- 新增日志不进入 JSON。

### 4.4 695 张关键回归

v1.1 重新扫描完整 695 张测试图片，与既有 `submission_reviewed_v2.json` 对比：

| 检查项 | 结果 |
|---|---:|
| 数量 | 695 / 695 |
| filename 差异 | 0 |
| width 差异 | 0 |
| height 差异 | 0 |
| label 差异 | 0 |
| 总记录差异 | 0 |
| 状态 | PASS |

当前候选分布仍为：有漂浮物 529、乱占 126、乱采 33、乱堆 6、乱建 1、正常 0。

这说明 v1.1 提升了可维护性、可观察性、内存和发布安全性，但没有偷偷改变模型效果或预测标签。

## 5. v1.1 正式包

使用补丁内正式构建器从当前真实四个权重重新生成：

```text
shuzhi_platform_inference_v1_1.tar.gz
```

- 大小：413,612,492 bytes；
- SHA256：`69851bec9c54892f4961ea8e06380cb8af768ef0ac96bd5d98574dbfcd4cc01a`；
- 归档文件数：11；
- checkpoint 数：4；
- 归档验收：PASS。

正式包仍只包含：六个运行文件、`checksums.sha256` 和四个 `fold*_best.pt`，不会把补丁工具、训练数据或 695 张图片带入平台包。

## 6. 当前建议

当前可以把 `shuzhi_platform_inference_v1_1.tar.gz` 作为正式平台上传候选。上传前只需要：

1. 用对应 `.sha256` 校验文件确认完整性；
2. 在平台环境运行一次 `python validate_runtime.py --device cpu` 或 `--device cuda`；
3. 用平台隐藏图片目录执行 `main.py`；
4. 保留标准输出中的耗时/显存日志，但提交文件只取 JSON。

v1.1 不会提高 mIoU/Weighted F1，因为它没有改模型、标签、权重或预测规则；它的价值是让当前候选结果更可靠、更省内存、更容易在平台环境复现和验收。
