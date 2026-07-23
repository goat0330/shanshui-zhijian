# competition/ — IAIC 算法主线

本目录负责 IAIC 水域异常智能识别赛道的完整算法链。与 `docs/` 产品链硬隔离：不依赖前端、数据库和工作流引擎。

## 目录职责

| 模块 | 职责 |
|------|------|
| `src/data/` | Dataset Adapter、数据审计、标签映射 |
| `src/inference/` | 模型加载、推理、输出解析 |
| `src/evaluation/` | 评测指标、场景切片、Bad Case |
| `src/submission/` | JSON 生成与 Schema 校验 |
| `configs/` | 模型配置、数据配置、任务配置 |
| `tests/` | 单元和集成测试 |

## 两条代理 Baseline

1. **视频检测链**：公开漂浮物数据 → 检测 → 后处理 → 评测
2. **遥感分类链**：公开水域遥感 → 分类/分割 → 评测

目标不是高指标，而是验证环境、接口、推理和评测流程。

## 约束

- 不依赖前端和数据库
- 模型可替换 — `DetectionResult` 是唯一跨链接口
- 官方数据不提交 Git（由 `src/data/` 适配器管理路径）
