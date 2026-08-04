# 赛题三正式离线推理包

这是可以交给比赛平台执行的单图六分类离线包。包内只包含推理脚本、运行时元数据和四个 `reviewed_v2` 四折 `last_stage` 最优权重，不包含训练集、测试集、标签文件、OOF、复核材料或旧提交文件。

## 运行

在任意工作目录执行：

```powershell
python path\to\shuzhi_platform_inference_v1\main.py `
  --input-dir path\to\hidden_images `
  --output path\to\submission.json
```

也可以显式指定 CPU：

```powershell
python path\to\shuzhi_platform_inference_v1\main.py --input-dir .\images --output .\submission.json --device cpu
```

支持递归扫描 `.jpg`、`.jpeg`、`.png`（大小写不敏感）。文件按 `path.name` 排序；输入目录中存在重复文件名会直接报错；输入目录至少要有一张图片。

## 输出格式

输出是 JSON 数组，每张图片一个对象，字段和值全部为字符串：

```json
[
    {
        "filename": "00000.jpg",
        "width": "4080",
        "height": "3060",
        "label": "有漂浮物"
    }
]
```

官方六类及固定顺序为：`乱采`、`乱建`、`乱堆`、`乱占`、`有漂浮物`、`正常`。

## 模型与离线边界

运行时使用 `timm.create_model("convnext_tiny", pretrained=False, num_classes=6)`，随后严格加载包内四个 checkpoint。不会下载预训练权重，不访问模型 Hub，也不依赖项目外的训练缓存。四折推理按 fold0→fold3 顺序逐个加载，单折完成后释放模型和 CUDA 缓存，再加载下一折；最终对四折 softmax 概率等权平均后取 argmax。

输入先做 EXIF 方向转正和 RGB 转换；模型输入使用 384 尺寸等比缩放+均值色填充、双三次插值和 ImageNet mean/std。输出宽高来自图片文件自身的原始尺寸。

## 运行时自检

```powershell
python path\to\shuzhi_platform_inference_v1\validate_runtime.py
```

自检会校验四个 checkpoint 的 SHA256、checkpoint 元数据和严格 state dict 加载。依赖版本见 `requirements.txt`；CUDA 版 PyTorch 应按平台现有 CUDA 环境安装，不要在平台上重新下载模型权重。
