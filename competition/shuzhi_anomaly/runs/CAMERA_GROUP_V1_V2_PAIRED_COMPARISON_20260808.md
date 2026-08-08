# Camera Group v1 / v2 配对对照

日期：2026-08-08

## 对照设计

两轮都使用相同配置：

- ConvNeXt-Tiny ImageNet-22K→1K
- 448×448
- reviewed_v2 标签
- head-only 5 epoch → last-stage 8 epoch
- backbone lr 5e-6、head lr 5e-5
- standard sampler、CE、AMP、seed 42
- 不使用旧 Fold checkpoint

唯一变量是 CV manifest：

- v1 对照：`internal_cv_duplicate_near_4fold.csv`
- v2 严格分组：人工修复后的 `camera_groupfold_manifest.csv`

## 全局结果

| 版本 | Weighted F1 | mIoU | 乱堆 F1 | 乱占 F1 | 有漂浮物 Recall |
|---|---:|---:|---:|---:|---:|
| v1 fresh control | 0.952378 | 0.471086 | 0.829268 | 0.761062 | 0.997065 |
| v2 reviewed groups | 0.894460 | 0.224343 | 0.000000 | 0.590476 | 0.996086 |
| v1 → v2 | -0.057918 | -0.246743 | -0.829268 | -0.170585 | -0.000978 |

## 结论

这个配对实验确认：普通 v1 OOF 的主要问题不是单纯“训练不够”，而是同机位/同场景样本跨 Fold 后，模型可以依赖背景和固定机位获得虚高分。v2 把已确认的同机位序列合并后，乱堆在完全未见场景上的表现直接降为 0，说明跨场景泛化才是当前真实瓶颈。

这不是说 v2 模型可以直接提交。v2 结果的用途是重新建立可信裁判：它证明现有 448 模型在新场景上没有学到稳定的乱堆实体特征。

## 下一步

不要继续在旧 v1 OOF 上做超参筛选。后续任何乱堆方案必须同时看：

1. v2 GroupKFold 结果；
2. 乱堆场景完整留出结果；
3. 必要时再用平台提交做最终确认。

当前保留 86.77 平台冠军，不生成新提交包。
