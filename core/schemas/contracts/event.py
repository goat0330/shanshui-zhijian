"""
C0 — AnomalyEvent 版本化异常事件

V0 状态只允许:
  under_review, confirmed, rejected, needs_more_evidence

禁止使用: illegal, violation_confirmed, closed, dispatched

除非已有人工或业务规则证据支持。
Event 的状态迁移必须通过 ReviewDecision。
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class AnomalyEvent(BaseModel):
    """版本化异常事件。一个或多个 Candidate 经关联后形成的待研判业务事件。

    约束:
    - event_version 必填，每次状态变更递增
    - 审核不覆盖 Event 内嵌字段，追加 ReviewDecision 后递增 version
    - 状态迁移必须通过 ReviewDecision（Decision 仅用于自动规则记录）
    - candidate_refs 和 event_version 必填
    - Evidence 不支持立场时记录 missing_context
    """
    schema_version: str = Field("event.v0.1-internal", description="契约版本")
    event_id: str = Field(..., min_length=1, description="稳定事件 ID")
    event_version: int = Field(1, ge=1, description="事件版本号，每次变更递增")
    status: Literal["under_review", "confirmed", "rejected", "needs_more_evidence"] = Field(
        "under_review",
        description="研判状态。初始为 under_review；不自动输出 confirmed",
    )
    category: str = Field("unknown", description="事件类别: water_extent_change / suspected_floating / unknown")
    severity: str = Field("medium", description="严重度: low / medium / high / critical")

    # ── 场景 ────────────────────────────────────────────────────
    geometry: dict | None = Field(None, description="GeoJSON 几何（缺少可靠定位时可为空）")
    temporal_extent: dict | None = Field(None, description='{"start": "...", "end": "..."}')

    # ── 引用 ────────────────────────────────────────────────────
    candidate_refs: list[str] = Field(default_factory=list, description="关联的 DetectionCandidate ID 列表")
    evidence_bundle_refs: list[str] = Field(
        default_factory=list,
        description="关联的 EvidenceBundle ID 列表",
    )

    # ── 理由 ────────────────────────────────────────────────────
    reason_codes: list[str] = Field(default_factory=list, description="理由码枚举，如 sar_backscatter_decrease")
    missing_context: list[str] = Field(
        default_factory=list,
        description="缺失上下文（许可/边界/时相不足/另一模态缺失）",
    )

    # ── 版本历史 ────────────────────────────────────────────────
    previous_version_ref: str | None = Field(
        None,
        description="前一个 Event 版本 ID（event_id@version），用于追溯",
    )

    # ── 时间 ────────────────────────────────────────────────────
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="创建时间 (RFC 3339)",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="最后更新时间 (RFC 3339)",
    )
