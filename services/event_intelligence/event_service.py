"""
C3 — EventService

Candidate + EvidenceBundle → Event v1 under_review

要求:
1. 同一 Candidate 重复输入只产生一个 Event（幂等）
2. Event ID 稳定（基于 candidate_id）
3. Event v1 不可覆盖
4. Candidate 与 Event 分离（Candidate 不可被 Event 修改）
5. 一个 Event 可关联多个 Candidate，V0 先支持一个
6. 不自动输出 confirmed
7. 缺少许可或现场信息时写入 missing_context
8. 事件理由使用 reason_codes
9. 事件的状态迁移必须通过 ReviewDecision（Decision 仅用于自动规则审计）
"""

import hashlib
from datetime import datetime, timezone
from typing import Any
from core.schemas.contracts.candidate import DetectionCandidate
from core.schemas.contracts.evidence import EvidenceBundle
from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.review import ReviewDecision
from core.schemas.contracts.replay import ReplayEntry
from services.repositories.interfaces import Repository


class EventServiceError(Exception):
    pass


class EventConflictError(EventServiceError):
    """Event 版本冲突。"""
    pass


class InvalidTransitionError(EventServiceError):
    """不合法的状态转换。"""
    pass


class EventNotFoundError(EventServiceError):
    pass


class DuplicateEventError(EventServiceError):
    pass


class EventService:
    """Event 生命周期管理服务。

    职责:
    - 从 Candidate + Bundle 创建 Event v1
    - 管理 Event 版本（只递增不覆盖）
    - 通过 ReviewDecision 驱动状态变更
    - Review 追加式、不修改 Candidate/Observation/Evidence
    - 乐观并发控制
    """

    ALLOWED_ACTIONS = {"confirm", "reject", "reclassify", "needs_more_evidence"}

    # (当前状态, action) → 目标状态
    TRANSITIONS = {
        "under_review": {
            "confirm": "confirmed",
            "reject": "rejected",
            "needs_more_evidence": "needs_more_evidence",
            "reclassify": "under_review",  # 改类不改变状态
        },
        "needs_more_evidence": {
            "confirm": "confirmed",
            "reject": "rejected",
            "needs_more_evidence": "needs_more_evidence",
        },
        "confirmed": {},
        "rejected": {},
    }

    def __init__(self, repository: Repository):
        self.repo = repository

    # ── Event 创建 ──────────────────────────────────────────────

    @staticmethod
    def _compute_event_id(candidate_id: str) -> str:
        """从 candidate_id 生成稳定 Event ID。"""
        raw = f"event:v1:{candidate_id}"
        return f"evt_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"

    def create_event(
        self,
        candidate: DetectionCandidate | dict[str, Any],
        bundle: EvidenceBundle | str,
        idempotency_key: str | None = None,
    ) -> AnomalyEvent:
        """从 Candidate + Bundle 创建 Event v1 under_review。

        同一 Candidate 重复输入只产生一个 Event（幂等）。
        """
        # 幂等检查
        if idempotency_key:
            existing = self.repo.get_idempotency_result(idempotency_key)
            if existing:
                raise EventConflictError(
                    f"幂等键已存在: {idempotency_key} → {existing}"
                )

        candidate_id = self._candidate_value(candidate, "candidate_id")
        candidate_type = self._candidate_value(candidate, "candidate_type")
        candidate_geometry = self._candidate_value(candidate, "geometry")
        candidate_temporal = self._candidate_value(candidate, "temporal_extent", {})
        candidate_quality = self._candidate_value(candidate, "quality_summary")
        bundle_id = bundle if isinstance(bundle, str) else bundle.bundle_id
        modalities_missing = [] if isinstance(bundle, str) else bundle.modalities_missing

        event_id = self._compute_event_id(candidate_id)

        # 检查是否已有 Event
        existing_event = self.repo.get_event(event_id)
        if existing_event:
            raise DuplicateEventError(
                f"Candidate {candidate_id} 的 Event 已存在: {event_id}"
            )

        # 构建前一个版本引用
        previous_ref = None

        # 构建 missing_context
        missing = []
        if modalities_missing:
            missing.append(f"missing_modalities:{','.join(modalities_missing)}")
        if candidate_quality:
            vpr = candidate_quality.get("valid_pixel_ratio", 1.0)
            if vpr is not None and vpr < 0.5:
                missing.append("low_valid_pixel_ratio")

        # 初始为 under_review，不自动 confirmed
        event = AnomalyEvent(
            event_id=event_id,
            event_version=1,
            status="under_review",
            category=candidate_type,
            severity="unassessed",
            geometry=candidate_geometry,
            temporal_extent=self._temporal_dict(candidate_temporal),
            candidate_refs=[candidate_id],
            evidence_bundle_refs=[bundle_id],
            reason_codes=self._build_reason_codes(candidate),
            missing_context=missing,
            previous_version_ref=previous_ref,
        )

        # 持久化（事务：先保存 Event，最后保存幂等键）
        owns_transaction = self.repo.begin_transaction()
        try:
            self.repo.save_event(event, commit=False)
            self.repo.save_event_candidate_link(event.event_id, candidate_id, commit=False)
            self.repo.save_event_version(event, commit=False)
            replay_entry = ReplayEntry(
                replay_entry_id=f"rpl_000000_create_{event.event_id[-8:]}",
                event_ref=event.event_id,
                sequence_number=0,
                actor_type="system",
                actor_ref="event-service",
                action="event_created",
                object_type="event",
                object_ref=event.event_id,
                object_version=1,
                reason="candidate_intake",
                metadata={"candidate_id": candidate_id},
            )
            self.repo.append_replay_entry(replay_entry, commit=False)
            if idempotency_key:
                self.repo.save_idempotency_key(idempotency_key, event.event_id, commit=False)
            if owns_transaction:
                self.repo.commit()
        except Exception:
            if owns_transaction:
                self.repo.rollback()
            raise

        return event

    # ── 状态变更 ────────────────────────────────────────────────

    def apply_review_decision(self, review: ReviewDecision) -> tuple[AnomalyEvent, bool]:
        """应用 ReviewDecision 变更 Event 状态。

        返回: (更新后的 Event, 是否变更)
        """
        event = self.repo.get_event(review.event_ref)
        if event is None:
            raise EventNotFoundError(f"Event 不存在: {review.event_ref}")

        # 检查重复提交（同一 decision_id）— 必须先于状态机检查
        existing_review = self.repo.get_review_by_id(review.decision_id)
        if existing_review:
            return event, False  # 幂等：不重复执行

        # 乐观锁检查
        if review.base_event_version != event.event_version:
            raise EventConflictError(
                f"版本冲突: Event {event.event_id} 当前版本 {event.event_version}, "
                f"Review 期望版本 {review.base_event_version}"
            )

        # 检查 action 是否合法
        if review.action not in self.ALLOWED_ACTIONS:
            raise InvalidTransitionError(f"非法审核动作: {review.action}")

        current_status = event.status
        allowed = self.TRANSITIONS.get(current_status, {})
        if review.action not in allowed:
            raise InvalidTransitionError(
                f"非法状态转换: Event {event.event_id} 当前状态 {current_status}, "
                f"无法执行 {review.action}"
            )

        # 执行转换
        target_status = allowed[review.action]
        updates = {
            "status": target_status,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if review.action == "reclassify" and review.reason_code:
            updates["category"] = review.reason_code
        updated_event = event.new_version(**updates)

        # 确保 resulting_event_version 正确
        if review.resulting_event_version != updated_event.event_version:
            # auto-fix
            object.__setattr__(
                review,
                "resulting_event_version",
                updated_event.event_version,
            )

        # 持久化（事务：乐观锁 + Event 版本 + Review + Replay）
        owns_transaction = self.repo.begin_transaction()
        try:
            affected = self.repo.optimistic_update_event(
                updated_event,
                review.base_event_version,
                commit=False,
            )
            if affected == 0:
                self.repo.rollback()
                raise EventConflictError(f"Optimistic lock: {event.event_id} {review.base_event_version}")
            self.repo.save_event_version(updated_event, commit=False)
            self.repo.save_review(review, commit=False)
            # Replay (per-event sequence)
            seq = self.repo.get_latest_sequence_number(event.event_id) + 1
            replay_entry = ReplayEntry(
                replay_entry_id=f"rpl_{seq:06d}_rev_{event.event_id[-8:]}",
                event_ref=updated_event.event_id, sequence_number=seq,
                actor_type="human", actor_ref=review.reviewer_ref or "system",
                action="review_submitted", object_type="event", object_ref=updated_event.event_id,
                object_version=updated_event.event_version,
                reason=f"{review.action}: {review.comment or ''}",
                metadata={"decision_id": review.decision_id},
            )
            self.repo.append_replay_entry(replay_entry, commit=False)
            if owns_transaction:
                self.repo.commit()
        except EventConflictError:
            raise
        except Exception:
            if owns_transaction:
                self.repo.rollback()
            raise

        return updated_event, True

    # ── 辅助 ────────────────────────────────────────────────────

    @staticmethod
    def _infer_severity(score: float) -> str:
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        elif score >= 0.3:
            return "low"
        return "medium"

    @staticmethod
    def _candidate_value(
        candidate: DetectionCandidate | dict[str, Any],
        field: str,
        default: Any = None,
    ) -> Any:
        if isinstance(candidate, dict):
            return candidate.get(field, default)
        return getattr(candidate, field, default)

    @staticmethod
    def _temporal_dict(temporal: Any) -> dict:
        if hasattr(temporal, "model_dump"):
            return temporal.model_dump()
        return dict(temporal or {})

    @classmethod
    def _build_reason_codes(
        cls,
        candidate: DetectionCandidate | dict[str, Any],
    ) -> list[str]:
        codes = []
        if cls._candidate_value(candidate, "candidate_type") in {
            "water_extent_change",
            "water_gain",
            "water_loss",
        }:
            codes.append("sar_backscatter_decrease")
        return codes
