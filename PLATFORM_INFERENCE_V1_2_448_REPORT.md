# 赛题三平台推理 v1.2（448px）验收报告

更新时间：2026-08-04<br>
项目：山水智鉴/赛题三——水域综合异常识别

## 1. 替换决策

OpenChamber task `shuzhi-448-4fold-20260804` 已通过 canonical event 验收：`status=completed`、`artifacts_ok=true`。四折 448px reviewed_v2 continuation 的 Global OOF 优于当前 384px v1.1 候选，因此 v1.2 替换 v1.1 作为当前正式候选；v1.1 保留为回退候选。

| 指标 | raw_v1 冠军 | v1.1 reviewed_v2 384px | v1.2 reviewed_v2 448px | v1.2 - v1.1 |
|---|---:|---:|---:|---:|
| Weighted F1 | 0.979403 | 0.982875 | **0.984696** | +0.001821 |
| mIoU | 0.629527 | 0.639108 | **0.644923** | +0.005815 |
| Macro-F1 | 0.647091 | 0.652262 | **0.655452** | +0.003189 |
| Accuracy | 0.984197 | 0.986831 | **0.988586** | +0.001756 |
| 错误数 | 18 | 15 | **13** | -2 |

四折 Weighted F1：fold0 `0.983987`、fold1 `0.989647`、fold2 `0.984405`、fold3 `0.980647`。冠军和 384px checkpoint SHA 均保持不变。

## 2. v1.2 推理包

- 文件：`shuzhi_platform_inference_v1_2.tar.gz`；
- 大小：413,611,782 bytes；
- SHA256：`156df2c4460f59c6b3b504cd2a7658d63645ca0f5e4c1b7849eb9e9bd8ebcac5`；
- 归档验收：11 个文件、4 个 checkpoint，`status=ok`；
- 448px checkpoint SHA：记录于 `shuzhi_platform_inference_v1_2/checksums.sha256`。

本轮只新增独立的 `shuzhi_platform_inference_v1_2`，没有覆盖 `shuzhi_platform_inference_v1`。

## 3. 运行时验收

- Python 静态编译：通过；
- `validate_runtime.py --device cpu`：通过；
- `validate_runtime.py --device cuda`：通过；
- 四折 SHA256：全部匹配；
- strict state dict：四折全部通过；
- 标签顺序、384 原生模型 data_config、448 训练输入尺寸：全部通过。

448px checkpoint 的 `args.image_size` 是 448，但 timm 原生 `data_config.input_size` 仍是 `(3,384,384)`。v1.2 校验器已明确区分这两个元数据，不再把合法的模型原生配置误判为错误；实际推理仍按 manifest 的 448px ResizePad 执行。

## 4. 695 张回归

v1.2 动态入口 CUDA 推理结果：695 张，177.854 秒，3.908 张/秒，峰值显存 540.4 MB。

与 v1.1 reviewed_v2 384px 候选逐条比较：

| 检查项 | 结果 |
|---|---:|
| 记录数 | 695 / 695 |
| 唯一文件名 | 695 |
| filename 差异 | 0 |
| width/height 差异 | 0 |
| 输出字段/标签非法记录 | 0 |
| 标签变化 | 24 |

24 个标签变化来自模型分辨率切换，不是入口顺序或尺寸读取错误。v1.2 预测分布为：有漂浮物 524、乱占 135、乱采 33、乱堆 2、乱建 1、正常 0。

## 5. 当前交付结论

当前正式上传候选为 `shuzhi_platform_inference_v1_2.tar.gz`。v1.1 包和 384px 权重继续保留，若平台隐藏集结果不符合预期，可直接回退到 v1.1，不需要重新训练。
