# 山水智鉴 V0 — 产品词汇表

> 版本: v0.1
> 更新: 2026-07-26

---

| 术语 | English | 定义 | 前端显示 | 备注 |
|------|---------|------|----------|------|
| 异常候选 | Candidate | 算法产出的疑似水域异常图斑 | — | 核心对象 |
| 研判任务 | Review Task | under_review 状态 Event 的前端称呼 | "研判任务" | 冻结决策 |
| 异常事件 | Anomaly Event | confirmed 状态 Event 的前端称呼 | "异常事件" | 冻结决策 |
| 证据包 | Evidence Bundle | 同一 Candidate 的多源证据集合 | "证据" | — |
| 研判 | Review | 人工对 Candidate 做出决策 | "人工研判" | — |
| 操作回放 | Replay | 全操作顺序记录 | "操作回放" | — |
| 运行追溯 | Run Trace | 从 Candidate 追溯到 Run 的完整链路 | "运行追溯" | — |
| 持久性异常 | Persistent | 多次观测持续存在的异常 | "持久性" | 默认显示 |
| 瞬态异常 | Transient | 单次观测出现后消失的异常 | "瞬态" | 默认隐藏 |
| 不确定异常 | Uncertain | 可靠性不足待确认的异常 | "不确定" | 默认显示 |
| 本次运行排序分 | Sort Score | Candidate 在当前 Run 内的排序分值 | "本次运行排序分" | 禁止称为概率 |
| 本批候选排名 | Batch Rank | Candidate 在当前批次的排名 | "本批候选排名 n / m" | 禁止称为准确率 |
| 变化类型 | Change Type | 异常变化的具体类别 | "变化类型" | — |
| 发生次数 | Occurrence Count | 异常在时间序列中出现的次数 | "发生次数" | — |
| 持久性比率 | Persistence Ratio | 异常持久程度的比率指标 | "持久性比率" | — |
| 代表性几何 | Representative Geometry | Candidate 最具代表性的空间几何 | "代表几何" | — |
| 合并几何 | Union Geometry | 多次观测结果的几何并集 | "合并几何" | — |
| 置信度 | Confidence | 算法对检测结果的置信程度 | — | 禁止展示为百分比 |
| 来源模态 | Source Modality | 证据来源的传感器类型 | "来源模态" | — |
| 立场 | Stance | 证据对 Candidate 的支持程度 | "证据立场" | supporting/contradicting |
| 制品 | Artifact | Run 产出的文件 | "运行制品" | — |
| 溯源 | Provenance | 数据的来源和处理链路 | "溯源" | — |
| 冲突 | Conflict | 版本冲突导致 Review 提交失败 | "版本冲突" | — |
| 治理事件 | Governance Event | 经过人工确认进入管理流程的事件 | "事件" | — |
