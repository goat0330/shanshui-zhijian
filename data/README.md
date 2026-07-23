# 数据目录

## 目录约定

| 目录 | 用途 | Git 追踪 |
|------|------|----------|
| `raw/` | 官方原始数据（只读） | ❌ .gitignore |
| `processed/` | 清洗对齐后的数据 | ❌ .gitignore |
| `external/` | 代理数据、公开数据集 | ❌ .gitignore |

## 原则

1. **官方数据永不提交 Git** — 即使后续训练集和测试集公布，也只通过脚本读取。
2. **代理数据存放在 `external/`**，来源标注在 `docs/04_证据与风险台账.md`。
3. 所有数据完整路径、MD5 和下载来源记录在 `data/` 根目录的 `MANIFEST.json`（待创建）。

## 数据适配器

数据读取统一通过 `competition/src/data/` 下的 Dataset Adapter 完成，替换数据源只需切换适配器和标签映射。
