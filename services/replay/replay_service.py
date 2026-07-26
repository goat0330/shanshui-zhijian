"""
C6 — ReplayService

输出完整时间线：
candidate_received → evidence_assembled → event_created_v1
→ review_submitted → event_created_v2 → status_changed

要求:
- sequence_number 连续
- 时间线不可覆盖
- 能区分 system、model、human
- 每个节点有 object_ref 和 version
- Replay 不通过读取当前状态猜测历史
- Repository 重启后仍可重建同样时间线
"""

from typing import Sequence
from core.schemas.contracts.replay import ReplayEntry
from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.review import ReviewDecision
from services.repositories.interfaces import Repository


class ReplayServiceError(Exception):
    pass


class ReplayService:
    """不可变事件时间线服务。

    Replay 不通过读取当前状态猜测历史。
    每个时间点的事件写入独立的 replay_entry。
    """

    def __init__(self, repository: Repository):
        self.repo = repository

    def record_candidate_received(
        self, event_ref: str, candidate_id: str, metadata: dict | None = None,
    ) -> ReplayEntry:
        """记录 candidate_received 事件。"""
        return self._append_entry(
            event_ref=event_ref,
            actor_type="system",
            actor_ref="candidate_intake",
            action="candidate_received",
            object_type="candidate",
            object_ref=candidate_id,
            reason="Candidate intake completed",
            metadata=metadata or {},
        )

    def record_evidence_assembled(
        self, event_ref: str, bundle_id: str, modalities_present: list[str],
        modalities_missing: list[str], metadata: dict | None = None,
    ) -> ReplayEntry:
        """记录 evidence_assembled 事件。"""
        return self._append_entry(
            event_ref=event_ref,
            actor_type="system",
            actor_ref="evidence_assembler",
            action="evidence_assembled",
            object_type="evidence_bundle",
            object_ref=bundle_id,
            reason=f"Evidence assembled. Present: {modalities_present}, Missing: {modalities_missing}",
            metadata=metadata or {},
        )

    def record_event_created(
        self, event: AnomalyEvent, metadata: dict | None = None,
    ) -> ReplayEntry:
        """记录 event_created 事件。"""
        return self._append_entry(
            event_ref=event.event_id,
            actor_type="system",
            actor_ref="event_service",
            action="event_created",
            object_type="event",
            object_ref=event.event_id,
            object_version=event.event_version,
            reason=f"Event v{event.event_version} created, status={event.status}",
            metadata=metadata or {},
        )

    def record_review_submitted(
        self, review: ReviewDecision, event_version: int, metadata: dict | None = None,
    ) -> ReplayEntry:
        """记录 review_submitted 事件。"""
        return self._append_entry(
            event_ref=review.event_ref,
            actor_type="human",
            actor_ref=review.reviewer_ref or "unknown",
            action="review_submitted",
            object_type="event",
            object_ref=review.event_ref,
            object_version=event_version,
            reason=f"{review.action}: {review.comment or ''}",
            metadata=metadata or {"decision_id": review.decision_id},
        )

    def record_event_version_created(
        self, event: AnomalyEvent, metadata: dict | None = None,
    ) -> ReplayEntry:
        """记录 event_version_created 事件。"""
        return self._append_entry(
            event_ref=event.event_id,
            actor_type="system",
            actor_ref="event_service",
            action="event_version_created",
            object_type="event",
            object_ref=event.event_id,
            object_version=event.event_version,
            reason=f"Event v{event.event_version}, status={event.status}",
            metadata=metadata or {},
        )

    def get_timeline(self, event_ref: str) -> Sequence[ReplayEntry]:
        """获取 Event 的完整时间线。"""
        return self.repo.get_replay_for_event(event_ref)

    def _append_entry(
        self,
        event_ref: str,
        actor_type: str,
        actor_ref: str,
        action: str,
        object_type: str,
        object_ref: str,
        object_version: int | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> ReplayEntry:
        """追加 Replay 条目。"""
        seq = self.repo.get_latest_sequence_number() + 1
        entry = ReplayEntry(
            replay_entry_id=f"rpl_{seq:06d}_{action}",
            event_ref=event_ref,
            sequence_number=seq,
            actor_type=actor_type,
            actor_ref=actor_ref,
            action=action,
            object_type=object_type,
            object_ref=object_ref,
            object_version=object_version,
            reason=reason,
            metadata=metadata or {},
        )
        self.repo.append_replay_entry(entry)
        return entry
