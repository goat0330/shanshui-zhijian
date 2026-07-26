"""
C4 — ReviewService

追加式审核决策服务。

要求:
1. confirm: under_review → confirmed
2. reject: under_review → rejected
3. needs_more_evidence: under_review → needs_more_evidence
4. reclassify: 生成 Event 新版本，保留旧版本
5. ReviewDecision 只能追加
6. Review 不得修改 Candidate、Observation 或 Evidence
7. 使用 base_event_version 进行乐观并发
8. 基于旧 Event 版本提交 Review 时返回 version_conflict
9. 同一 decision_id 重复提交不重复执行（幂等）
10. 所有状态变化写 Replay
"""

from typing import Literal
from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.review import ReviewDecision
from services.event_intelligence.event_service import EventService, EventNotFoundError, EventConflictError


class ReviewServiceError(Exception):
    pass


class ReviewService:
    """追加式审核决策服务。"""

    def __init__(self, event_service: EventService):
        self.event_service = event_service

    def confirm(
        self,
        event_id: str,
        reviewer: str,
        comment: str | None = None,
        reason_code: str | None = None,
        decision_id: str | None = None,
    ) -> tuple[AnomalyEvent, bool]:
        """确认：under_review → confirmed"""
        # 读 Event 获取当前版本
        event = self.event_service.repo.get_event(event_id)
        if event is None:
            raise EventNotFoundError(f"Event 不存在: {event_id}")

        review = ReviewDecision(
            decision_id=decision_id or f"rev_confirm_{event_id}_{event.event_version}",
            event_ref=event_id,
            base_event_version=event.event_version,
            action="confirm",
            reason_code=reason_code,
            comment=comment,
            reviewer_ref=reviewer,
            resulting_event_version=event.event_version + 1,
        )
        return self.event_service.apply_review_decision(review)

    def reject(
        self,
        event_id: str,
        reviewer: str,
        comment: str | None = None,
        reason_code: str | None = None,
        decision_id: str | None = None,
    ) -> tuple[AnomalyEvent, bool]:
        """驳回：under_review → rejected"""
        event = self.event_service.repo.get_event(event_id)
        if event is None:
            raise EventNotFoundError(f"Event 不存在: {event_id}")

        review = ReviewDecision(
            decision_id=decision_id or f"rev_reject_{event_id}_{event.event_version}",
            event_ref=event_id,
            base_event_version=event.event_version,
            action="reject",
            reason_code=reason_code,
            comment=comment,
            reviewer_ref=reviewer,
            resulting_event_version=event.event_version + 1,
        )
        return self.event_service.apply_review_decision(review)

    def needs_more_evidence(
        self,
        event_id: str,
        reviewer: str,
        comment: str | None = None,
        reason_code: str | None = None,
        decision_id: str | None = None,
    ) -> tuple[AnomalyEvent, bool]:
        """要求补证：under_review → needs_more_evidence"""
        event = self.event_service.repo.get_event(event_id)
        if event is None:
            raise EventNotFoundError(f"Event 不存在: {event_id}")

        review = ReviewDecision(
            decision_id=decision_id or f"rev_need_ev_{event_id}_{event.event_version}",
            event_ref=event_id,
            base_event_version=event.event_version,
            action="needs_more_evidence",
            reason_code=reason_code,
            comment=comment,
            reviewer_ref=reviewer,
            resulting_event_version=event.event_version + 1,
        )
        return self.event_service.apply_review_decision(review)

    def reclassify(
        self,
        event_id: str,
        new_category: str,
        reviewer: str,
        comment: str | None = None,
        reason_code: str | None = None,
        decision_id: str | None = None,
    ) -> tuple[AnomalyEvent, bool]:
        """改类：生成 Event 新版本，保留旧版本。

        使用 reason_code 传递新的类别。
        """
        event = self.event_service.repo.get_event(event_id)
        if event is None:
            raise EventNotFoundError(f"Event 不存在: {event_id}")

        review = ReviewDecision(
            decision_id=decision_id or f"rev_recls_{event_id}_{event.event_version}",
            event_ref=event_id,
            base_event_version=event.event_version,
            action="reclassify",
            reason_code=new_category,  # 使用 reason_code 传递新类别
            comment=comment,
            reviewer_ref=reviewer,
            resulting_event_version=event.event_version + 1,
        )
        return self.event_service.apply_review_decision(review)

    def apply_review_decision(self, review: ReviewDecision) -> tuple[AnomalyEvent, bool]:
        """通用入口：应用一条 ReviewDecision。"""
        return self.event_service.apply_review_decision(review)
