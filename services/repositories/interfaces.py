"""
C5 — Repository 抽象接口

用于服务层与存储层解耦。
当前实现为 SQLite，接口允许未来替换为 PostgreSQL。
"""

from abc import ABC, abstractmethod
from typing import Sequence
from core.schemas.contracts.evidence import Evidence, EvidenceBundle
from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.review import ReviewDecision
from core.schemas.contracts.replay import ReplayEntry


class Repository(ABC):
    """Repository 抽象接口。"""

    # ── Evidence ────────────────────────────────────────────────
    @abstractmethod
    def save_evidence(self, evidence: Evidence) -> Evidence:
        ...

    @abstractmethod
    def get_evidence(self, evidence_id: str) -> Evidence | None:
        ...

    @abstractmethod
    def list_evidence(self, candidate_ref: str | None = None) -> Sequence[Evidence]:
        ...

    # ── EvidenceBundle ──────────────────────────────────────────
    @abstractmethod
    def save_evidence_bundle(self, bundle: EvidenceBundle) -> EvidenceBundle:
        ...

    @abstractmethod
    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundle | None:
        ...

    # ── AnomalyEvent ────────────────────────────────────────────
    @abstractmethod
    def save_event(self, event: AnomalyEvent) -> AnomalyEvent:
        ...

    @abstractmethod
    def get_event(self, event_id: str) -> AnomalyEvent | None:
        ...

    @abstractmethod
    def list_events(self) -> Sequence[AnomalyEvent]:
        ...

    @abstractmethod
    def get_event_by_candidate(self, candidate_id: str) -> AnomalyEvent | None:
        """通过 candidate_id 查找已关联的 Event。"""
        ...

    @abstractmethod
    def save_event_candidate_link(self, event_id: str, candidate_id: str) -> None:
        ...

    # ── ReviewDecision ──────────────────────────────────────────
    @abstractmethod
    def save_review(self, review: ReviewDecision) -> ReviewDecision:
        ...

    @abstractmethod
    def get_reviews_for_event(self, event_id: str) -> Sequence[ReviewDecision]:
        ...

    @abstractmethod
    def get_review_by_id(self, decision_id: str) -> ReviewDecision | None:
        ...

    # ── Replay ──────────────────────────────────────────────────
    @abstractmethod
    def append_replay_entry(self, entry: ReplayEntry) -> ReplayEntry:
        ...

    @abstractmethod
    def get_replay_for_event(self, event_ref: str) -> Sequence[ReplayEntry]:
        ...

    @abstractmethod
    def get_latest_sequence_number(self) -> int:
        ...

    # ── Idempotency ─────────────────────────────────────────────
    @abstractmethod
    def save_idempotency_key(self, key: str, result_ref: str) -> None:
        ...

    @abstractmethod
    def get_idempotency_result(self, key: str) -> str | None:
        """返回之前保存的 result_ref，或 None。"""
        ...

    # ── Transaction ─────────────────────────────────────────────
    @abstractmethod
    def begin_transaction(self):
        ...

    @abstractmethod
    def commit(self):
        ...

    @abstractmethod
    def rollback(self):
        ...

    @abstractmethod
    def close(self):
        ...
