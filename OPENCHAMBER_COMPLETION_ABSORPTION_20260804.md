# OpenChamber 本轮完成态吸收记录

更新时间：2026-08-04<br>
项目：赛题三——水域综合异常识别<br>
任务工作目录：`D:\研究生作业\人工智能实践比赛\competition\shuzhi_anomaly`

## 1. Canonical 完成证据

本轮通过 OpenChamber supervisor 的 `event-read` 读取 canonical event，而不是把 session 的 `idle` 状态当作训练完成证明：

| 字段 | 值 |
|---|---|
| task_id | `shuzhi-overnight-20260804` |
| event_id | `evt_71bde48f1808411795b785c3e1918162` |
| session_id | `ses_037229559ffeXuWP1YVcFSn0Br` |
| status | `completed` |
| artifacts_ok | `true` |
| ready_for_next_task | `true` |

事件声明的四项产物均已存在：

- `runs/overnight_20260804/01_reviewed_v2_4fold/`
- `runs/overnight_20260804/04_oof_compare/global_oof_gate_comparison.json`
- `runs/overnight_20260804/05_test_inference/submission_reviewed_v2.json`
- `runs/overnight_20260804/06_final_report/OVERNIGHT_SUMMARY.md`

注意：事件中的相对路径必须以 `competition/shuzhi_anomaly` 为 base directory 解析。若误以项目根目录解析，会得到产物不存在的假阴性；使用任务工作目录复核后四项全部通过。

## 2. 本轮阶段结果

| 阶段 | 结果 | 含义 |
|---|---|---|
| 00 preflight | 通过 | CUDA、环境、冠军权重 SHA 和严格复核 CSV 均通过 |
| 01 reviewed_v2 四折续训 | 完成 | fold0–fold3 均写出 best/last checkpoint，无 NaN/Inf |
| 02 block0005 holdout | 完成，诊断-only | 801 张几乎全为有漂浮物，分数虚高，不作为主验证 |
| 03 448px fold2 | 完成，诊断-only | Weighted F1 0.984405，错误 4→3，建议后续扩展四折 |
| 04 Global OOF gate | PASS | reviewed_v2 Weighted F1 0.982875，高于冠军 0.979403 |
| 05 测试推理 | 通过 | 695 条 JSON、六类标签、文件名/尺寸/重复检查通过 |
| 06 final report | 完成 | 环境、指标、权重 SHA 和候选提交均已归档 |

## 3. 当前模型决策

reviewed_v2 四折续训确定为候选 B，原 `repair_v2` 四折冠军保留为候选 A。reviewed_v2 的 Global OOF 为：

- Weighted F1：`0.9828751037`；
- mIoU：`0.6391082814`；
- Macro-F1：`0.6522623068`；
- Accuracy：`0.9868305531`；
- 错误数：15；
- 有漂浮物 Recall：`0.9990215264`。

当前 695 张候选提交 `submission_reviewed_v2.json` 已通过格式校验，预测分布为：有漂浮物 529、乱占 126、乱采 33、乱堆 6、乱建 1、正常 0。`正常` 和 `乱建` 的低预测数是模型能力风险，不是平台推理入口引入的变化。

## 4. 与当前平台推理包的关系

本轮训练产物已被当前 v1.1 平台推理包吸收：四个 reviewed_v2 checkpoint、四折等权概率平均、384 ResizePad 和四字段 JSON 输出契约保持一致。v1.1 只做推理工程加固，不改变模型权重、标签、预处理规则或预测结果。

因此当前正式候选链为：

```text
OpenChamber reviewed_v2 训练完成
→ Global OOF gate PASS
→ 695 张候选 JSON 验证通过
→ v1.1 平台推理入口 695 张逐条回归零差异
→ 使用 shuzhi_platform_inference_v1_1.tar.gz 作为正式上传候选
```

## 5. 后续边界

事件建议的后续工作是完整四折 448px 扩展，以及候选 A/B 的平台结果比较。在没有新训练结果前，不把 448 单折诊断直接替换为正式主线，也不覆盖原冠军 checkpoint。
