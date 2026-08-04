# 赛题三正式离线推理包 v1.1

这是比赛平台执行的单图六分类离线推理包。正式包只包含推理脚本、运行时元数据和四个 `reviewed_v2` 四折 `last_stage` 最优权重，不包含训练集、测试集、标签文件、OOF、复核材料或旧提交文件。

## 平台契约

当前入口是通用 CLI：

```bash
python main.py --input-dir /path/to/hidden_images --output /path/to/submission.json
```

若比赛平台规定固定入口文件、固定输入环境变量、固定输出路径、Docker 或 `run.sh`，必须以官方平台规范为准，并让平台包装器调用上述入口。不要仅凭本包假设平台会自动执行该命令。

## 依赖策略

`requirements.txt` 只列出非框架依赖。平台应优先使用预装、与其 CUDA 驱动匹配的 `torch` 和 `torchvision`，不要无条件运行普通 pip 命令覆盖平台 CUDA 环境。

本机完整复现版本见补丁包中的 `requirements-full-local.txt`：

```text
torch==2.6.0
torchvision==0.21.0
timm==1.0.28
Pillow==11.3.0
```

## 运行

```bash
python main.py \
  --input-dir /path/to/hidden_images \
  --output /path/to/submission.json \
  --device auto \
  --batch-size 16 \
  --workers 0
```

支持递归扫描 `.jpg`、`.jpeg`、`.png`，后缀大小写不敏感。文件按 filename 稳定排序；不同子目录出现同名文件会直接报错；输入至少包含一张图片。

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

官方六类固定顺序：`乱采`、`乱建`、`乱堆`、`乱占`、`有漂浮物`、`正常`。

## 模型和集成

运行时使用 `timm.create_model("convnext_tiny", pretrained=False, num_classes=6)`，随后严格加载包内权重，不访问网络或模型 Hub。四折按 manifest 顺序逐个加载，每折完成后释放模型；概率使用 manifest 中的权重做 running-sum 集成，默认权重均为 0.25。

输入先做 EXIF 转正和 RGB 转换；模型输入使用 384 尺寸等比缩放、均值色填充、BICUBIC 和 ImageNet mean/std。输出宽高来自文件原始尺寸。

## 运行时自检

```bash
python validate_runtime.py --device cpu
```

自检复用正式推理的完整加载路径，会验证：

- checkpoint SHA256；
- 标签顺序、fold、模型名和 freeze mode；
- 输入尺寸、插值、mean/std；
- strict state-dict 加载。

## 正式归档验收

补丁包 `tools/` 中包含：

- `build_platform_package.py`：从四个现有权重构建白名单正式包；
- `verify_release_archive.py`：检查归档路径安全、成员白名单、checksums 和权重 SHA；
- `apply_patch.ps1`：覆盖现有核心目录。
