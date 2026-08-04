# 赛题三正式离线推理包审计

## 结论

`shuzhi_platform_inference_v1.tar.gz` 已完成构建，作为赛题三“每张图片输出一个 label”的正式离线推理包候选上传。ZIP 仅作为备用格式保留。包内没有训练数据、测试数据、训练标签、OOF、复核材料、旧提交 JSON、固定测试 manifest、HF cache 或项目绝对路径。

本次工作在独立 worktree 和分支 `feat/platform-inference-v1` 完成，未修改稳定 `main`，未修改原始图片和原始 checkpoint。

## 任务与输出契约

已核对的赛题材料确认任务是六分类，评分核心为加权 F1。当前交接要求的正式输出契约为 JSON 数组，每条记录只包含以下四个字段，字段和值均为字符串：

```json
{
    "filename": "00000.jpg",
    "width": "4080",
    "height": "3060",
    "label": "有漂浮物"
}
```

固定标签顺序为：`乱采`、`乱建`、`乱堆`、`乱占`、`有漂浮物`、`正常`。

由于现有材料没有提供隐藏运行器的 Docker、入口脚本、超时和资源限制说明，包提供通用 CLI 入口，平台如有包装器只需调用 `main.py`。

## 模型实现

- 模型架构：`timm` 的 `convnext_tiny`，分类数 6。
- 运行时使用 `pretrained=False` 创建模型，再严格加载包内权重；不会下载模型或访问网络。
- 四个 checkpoint 均为 `reviewed_v2` 四折 `last_stage` `best.pt`。
- 推理顺序为 fold0→fold3；单折完成后释放模型并清理 CUDA cache，不同时占用四个模型的 GPU 显存。
- 四折输出先做 softmax，再等权平均，最后 argmax。
- 预处理复刻训练验证链路：EXIF 转正、RGB、384 尺寸等比缩放+均值色填充、BICUBIC、ImageNet mean/std；不使用 CenterCrop。
- 输出宽高取图片文件的原始 `Image.open(...).size`。

四个权重 SHA256：

| Fold | 文件 | SHA256 |
|---:|---|---|
| 0 | `weights/fold0_best.pt` | `d177b6e8af8f37f7129e45df4d636865dcb82bab624b7cfc2aa21d1d2c2d3899` |
| 1 | `weights/fold1_best.pt` | `704d5c28e5a3b87ddea75e8a51116000124ee4b9e1aa81c4a523038d87564297` |
| 2 | `weights/fold2_best.pt` | `de9000c830abe3606a4a7f4d2c7575f2cc0745c5a7dd417833f10091daa30664` |
| 3 | `weights/fold3_best.pt` | `5f32f1ab6bc4cd97f3d72699892d791b88c2346e15767590e6e69514b8ab0c64` |

## 正式包文件清单

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

正式 tar.gz 大小：413,611,044 bytes；SHA256：`996443fdd47a4dbbb71ca8e2d1659e2c11c5b988f92ff5b71b2d55c98281c6b6`。备用 ZIP 大小：413,223,037 bytes；未压缩正式包文件总大小：445,506,899 bytes。

## 验证结果

1. 运行时自检：通过。Python 3.11.5、torch 2.6.0+cu118、torchvision 0.21.0+cu118、timm 1.0.28、Pillow 11.3.0；四折 SHA256 和 strict state-dict load 全部通过。
2. 动态小样本：11 张混合 JPG/PNG，包含嵌套目录、横向/纵向和不同分辨率；CUDA 通过，CPU 通过，CPU/CUDA 输出完全一致；字段、字符串类型、标签集合和排序通过。
3. 隔离测试：从非项目工作目录执行，使用独立复制的推理包、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1` 和 socket 网络阻断器；11 张推理通过，未触发网络访问。
4. 695 张一致性：与现有 `submission_reviewed_v2.json` 逐条对比，数量 695、文件名顺序一致、宽高差异 0、标签差异 0、总记录差异 0。详细结果见 `platform_695_consistency/consistency_report.json`，差异文件见 `platform_695_consistency/prediction_diff.csv`。
5. 压缩包审计：正式 tar.gz 内恰好 11 个正式文件；无 `__pycache__`、训练文件、测试 manifest、`last.pt` 或旧模型目录。tar.gz SHA256 已写入 `shuzhi_platform_inference_v1.tar.gz.sha256`；备用 ZIP 也已完成同样校验。

## 已知边界

- 695 张是无标签测试图，因此一致性测试只能证明“新入口复现现有候选提交”，不能证明隐藏测试集得分。
- 现有候选模型在 695 张上的预测分布仍是：有漂浮物 529、乱占 126、乱采 33、乱堆 6、乱建 1、正常 0。这是模型能力风险，不是推理包格式或入口错误。
- 平台若锁定了不同的 CUDA/PyTorch 版本，应按 `requirements.txt` 和平台 CUDA 约束准备运行环境；包本身不携带 CUDA runtime。
