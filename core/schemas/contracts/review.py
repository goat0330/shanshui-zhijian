"""
C0 — ReviewDecision

ReviewDecision 只允许追加，不允许 update 和 delete。
action 只允许: confirm, reject, reclassify, needs_more_evidence
使用 base_event_version 实现乐观并发控制。
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ReviewDecision(BaseModel):
    """追加式人工审核决策。

    只允许追加，不允许 update 和 delete。
    使用 base_event_version 实现乐观并发。
    基于旧 Event 版本提交 Review 时返回 version_conflict。
    """
    decision_id: str = Field(..., min_length=1, description="审核决策 ID，全局唯一")
    event_ref: str = Field(..., min_length=1, description="关联 Event ID")
    base_event_version: int = Field(..., ge=1, description="期望的 Event 版本号（乐观锁）")

    action: Literal["confirm", "reject", "reclassify", "needs_more_evidence"] = Field(
        ...,
        description="审核动作: confirm=确认, reject=驳回, reclassify=改类, needs_more_evidence=补证",
    )
    reason_code: str | None = Field(None, description="原因码枚举")
    comment: str | None = Field(None, description="审核评论文本")

    reviewer_ref: str = Field("", description="审核人引用（用户名/ID）")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="补充的证据引用（补证时使用）",
    )

    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="审核时间 (RFC 3339)",
    )
    resulting_event_version: int = Field(
        ...,
        ge=1,
        description="审核后的 Event 版本号（预期 = base_event_version + 1）",
    )


class Decision(BaseModel):
    """规则或模型做出的自动决策步骤。

    用于审计和追溯，不直接驱动 Event 状态变更。
    """
    decision_id: str = Field(..., min_length=1, description="决策 ID")
    event_ref: str = Field(..., min_length=1, description="关联 Event ID")
    decision_type: str = Field(..., description="auto_suppress / auto_confirm / rule_match / quality_reject")
    input_refs: list[str] = Field(default_factory=list, description="输入引用")
    rule_version: str = Field("", description="规则版本")
    output: dict = Field(default_factory=dict, description="决策输出")
    reason_codes: list[str] = Field(default_factory=list, description="理由码")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="决策时间 (RFC 3339)",
    )
