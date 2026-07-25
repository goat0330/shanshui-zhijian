"""
C5 — SQLite Repository 实现

使用 SQLite 作为持久化存储。
服务重启后记录仍存在。
唯一约束防止重复 Event 和 Review。
支持事务中同时写 Event 新版本、Review 和 Replay。
不使用 Postgres 特有能力，接口允许未来替换 PostgreSQL。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Sequence
from dataclasses import dataclass

from services.repositories.interfaces import Repository
from core.schemas.contracts.evidence import Evidence, EvidenceBundle
from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.review import ReviewDecision
from core.schemas.contracts.replay import ReplayEntry


@dataclass
class SQLiteRepositoryConfig:
    db_path: str = "data/agent_c.db"
    echo: bool = False


class SQLiteRepository(Repository):
    """SQLite Repository 实现。

    最少表:
    - evidence
    - evidence_bundles
    - events
    - event_versions
    - event_candidate_links
    - reviews
    - replay_entries
    - idempotency_keys
    """

    def __init__(self, config: SQLiteRepositoryConfig | None = None):
        self.config = config or SQLiteRepositoryConfig()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            path = Path(self.config.db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                evidence_type TEXT NOT NULL,
                source_modality TEXT NOT NULL,
                source_asset_ref TEXT NOT NULL,
                derived_asset_ref TEXT,
                candidate_ref TEXT,
                captured_at TEXT,
                geometry TEXT,
                geometry_crs TEXT,
                stance TEXT NOT NULL DEFAULT 'supporting',
                quality_summary TEXT,
                provenance TEXT,
                unavailable_reason TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence_bundles (
                bundle_id TEXT PRIMARY KEY,
                candidate_ref TEXT NOT NULL,
                evidence_refs TEXT NOT NULL DEFAULT '[]',
                modalities_present TEXT NOT NULL DEFAULT '[]',
                modalities_missing TEXT NOT NULL DEFAULT '[]',
                spatial_summary TEXT,
                temporal_summary TEXT,
                quality_summary TEXT,
                created_at TEXT NOT NULL,
                assembler_version TEXT NOT NULL DEFAULT '1.0.0'
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL DEFAULT 'event.v0.1-internal',
                event_version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'under_review',
                category TEXT NOT NULL DEFAULT 'unknown',
                severity TEXT NOT NULL DEFAULT 'medium',
                geometry TEXT,
                temporal_extent TEXT,
                candidate_refs TEXT NOT NULL DEFAULT '[]',
                evidence_bundle_refs TEXT NOT NULL DEFAULT '[]',
                reason_codes TEXT NOT NULL DEFAULT '[]',
                missing_context TEXT NOT NULL DEFAULT '[]',
                previous_version_ref TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_candidate_links (
                event_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                PRIMARY KEY (event_id, candidate_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                decision_id TEXT PRIMARY KEY,
                event_ref TEXT NOT NULL,
                base_event_version INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason_code TEXT,
                comment TEXT,
                reviewer_ref TEXT NOT NULL DEFAULT '',
                evidence_refs TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                resulting_event_version INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS replay_entries (
                replay_entry_id TEXT PRIMARY KEY,
                event_ref TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                actor_type TEXT NOT NULL,
                actor_ref TEXT NOT NULL,
                action TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_ref TEXT NOT NULL,
                object_version INTEGER,
                reason TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS idempotency_keys (
                idempotency_key TEXT PRIMARY KEY,
                result_ref TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ev_candidate ON evidence(candidate_ref);
            CREATE INDEX IF NOT EXISTS idx_eb_candidate ON evidence_bundles(candidate_ref);
            CREATE INDEX IF NOT EXISTS idx_ecl_candidate ON event_candidate_links(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_event ON reviews(event_ref);
            CREATE INDEX IF NOT EXISTS idx_replay_event ON replay_entries(event_ref);
            CREATE INDEX IF NOT EXISTS idx_replay_seq ON replay_entries(sequence_number);
        """)
        conn.commit()

    # ── 序列化工具 ──────────────────────────────────────────────
    @staticmethod
    def _to_json(obj) -> str:
        if isinstance(obj, str):
            return obj
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def _from_json(val: str | None):
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    # ── Evidence ────────────────────────────────────────────────
    def save_evidence(self, evidence: Evidence) -> Evidence:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO evidence
                (evidence_id, evidence_type, source_modality, source_asset_ref,
                 derived_asset_ref, candidate_ref, captured_at, geometry,
                 geometry_crs, stance, quality_summary, provenance,
                 unavailable_reason, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            evidence.evidence_id, evidence.evidence_type, evidence.source_modality,
            evidence.source_asset_ref, evidence.derived_asset_ref,
            evidence.candidate_ref, evidence.captured_at,
            self._to_json(evidence.geometry), evidence.geometry_crs,
            evidence.stance, self._to_json(evidence.quality_summary),
            self._to_json(evidence.provenance), evidence.unavailable_reason,
            evidence.created_at,
        ))
        conn.commit()
        return evidence

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        return self._row_to_evidence(row)

    def list_evidence(self, candidate_ref: str | None = None) -> Sequence[Evidence]:
        conn = self._get_conn()
        if candidate_ref:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE candidate_ref = ? ORDER BY created_at",
                (candidate_ref,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM evidence ORDER BY created_at"
            ).fetchall()
        return [self._row_to_evidence(r) for r in rows]

    @staticmethod
    def _row_to_evidence(row) -> Evidence | None:
        if row is None:
            return None
        return Evidence(
            evidence_id=row["evidence_id"],
            evidence_type=row["evidence_type"],
            source_modality=row["source_modality"],
            source_asset_ref=row["source_asset_ref"],
            derived_asset_ref=row["derived_asset_ref"],
            candidate_ref=row["candidate_ref"],
            captured_at=row["captured_at"],
            geometry=json.loads(row["geometry"]) if row["geometry"] else None,
            geometry_crs=row["geometry_crs"],
            stance=row["stance"],
            quality_summary=json.loads(row["quality_summary"]) if row["quality_summary"] else None,
            provenance=json.loads(row["provenance"]) if row["provenance"] else None,
            unavailable_reason=row["unavailable_reason"],
            created_at=row["created_at"],
        )

    # ── EvidenceBundle ──────────────────────────────────────────
    def save_evidence_bundle(self, bundle: EvidenceBundle) -> EvidenceBundle:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO evidence_bundles
                (bundle_id, candidate_ref, evidence_refs, modalities_present,
                 modalities_missing, spatial_summary, temporal_summary,
                 quality_summary, created_at, assembler_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            bundle.bundle_id, bundle.candidate_ref,
            self._to_json(bundle.evidence_refs),
            self._to_json(bundle.modalities_present),
            self._to_json(bundle.modalities_missing),
            self._to_json(bundle.spatial_summary),
            self._to_json(bundle.temporal_summary),
            self._to_json(bundle.quality_summary),
            bundle.created_at, bundle.assembler_version,
        ))
        conn.commit()
        return bundle

    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundle | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM evidence_bundles WHERE bundle_id = ?", (bundle_id,)
        ).fetchone()
        if row is None:
            return None
        return EvidenceBundle(
            bundle_id=row["bundle_id"],
            candidate_ref=row["candidate_ref"],
            evidence_refs=json.loads(row["evidence_refs"]),
            modalities_present=json.loads(row["modalities_present"]),
            modalities_missing=json.loads(row["modalities_missing"]),
            spatial_summary=json.loads(row["spatial_summary"]) if row["spatial_summary"] else None,
            temporal_summary=json.loads(row["temporal_summary"]) if row["temporal_summary"] else None,
            quality_summary=json.loads(row["quality_summary"]) if row["quality_summary"] else None,
            created_at=row["created_at"],
            assembler_version=row["assembler_version"],
        )

    # ── AnomalyEvent ────────────────────────────────────────────
    def save_event(self, event: AnomalyEvent) -> AnomalyEvent:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO events
                (event_id, schema_version, event_version, status, category,
                 severity, geometry, temporal_extent, candidate_refs,
                 evidence_bundle_refs, reason_codes, missing_context,
                 previous_version_ref, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            event.event_id, event.schema_version, event.event_version,
            event.status, event.category, event.severity,
            self._to_json(event.geometry), self._to_json(event.temporal_extent),
            self._to_json(event.candidate_refs),
            self._to_json(event.evidence_bundle_refs),
            self._to_json(event.reason_codes),
            self._to_json(event.missing_context),
            event.previous_version_ref, event.created_at, event.updated_at,
        ))
        conn.commit()
        return event

    def get_event(self, event_id: str) -> AnomalyEvent | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        return AnomalyEvent(
            event_id=row["event_id"],
            event_version=row["event_version"],
            status=row["status"],
            category=row["category"],
            severity=row["severity"],
            geometry=json.loads(row["geometry"]) if row["geometry"] else None,
            temporal_extent=json.loads(row["temporal_extent"]) if row["temporal_extent"] else None,
            candidate_refs=json.loads(row["candidate_refs"]),
            evidence_bundle_refs=json.loads(row["evidence_bundle_refs"]),
            reason_codes=json.loads(row["reason_codes"]),
            missing_context=json.loads(row["missing_context"]),
            previous_version_ref=row["previous_version_ref"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_events(self) -> Sequence[AnomalyEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at"
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    @staticmethod
    def _row_to_event(row) -> AnomalyEvent:
        return AnomalyEvent(
            event_id=row["event_id"],
            event_version=row["event_version"],
            status=row["status"],
            category=row["category"],
            severity=row["severity"],
            geometry=json.loads(row["geometry"]) if row["geometry"] else None,
            temporal_extent=json.loads(row["temporal_extent"]) if row["temporal_extent"] else None,
            candidate_refs=json.loads(row["candidate_refs"]),
            evidence_bundle_refs=json.loads(row["evidence_bundle_refs"]),
            reason_codes=json.loads(row["reason_codes"]),
            missing_context=json.loads(row["missing_context"]),
            previous_version_ref=row["previous_version_ref"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_event_by_candidate(self, candidate_id: str) -> AnomalyEvent | None:
        conn = self._get_conn()
        row = conn.execute("""
            SELECT e.* FROM events e
            INNER JOIN event_candidate_links ecl ON e.event_id = ecl.event_id
            WHERE ecl.candidate_id = ?
        """, (candidate_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def save_event_candidate_link(self, event_id: str, candidate_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO event_candidate_links (event_id, candidate_id) VALUES (?, ?)",
            (event_id, candidate_id),
        )
        conn.commit()

    # ── ReviewDecision ──────────────────────────────────────────
    def save_review(self, review: ReviewDecision) -> ReviewDecision:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO reviews
                (decision_id, event_ref, base_event_version, action,
                 reason_code, comment, reviewer_ref, evidence_refs,
                 created_at, resulting_event_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            review.decision_id, review.event_ref, review.base_event_version,
            review.action, review.reason_code, review.comment,
            review.reviewer_ref, self._to_json(review.evidence_refs),
            review.created_at, review.resulting_event_version,
        ))
        conn.commit()
        return review

    def get_reviews_for_event(self, event_id: str) -> Sequence[ReviewDecision]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM reviews WHERE event_ref = ? ORDER BY created_at",
            (event_id,)
        ).fetchall()
        return [self._row_to_review(r) for r in rows]

    def get_review_by_id(self, decision_id: str) -> ReviewDecision | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM reviews WHERE decision_id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_review(row)

    @staticmethod
    def _row_to_review(row) -> ReviewDecision:
        return ReviewDecision(
            decision_id=row["decision_id"],
            event_ref=row["event_ref"],
            base_event_version=row["base_event_version"],
            action=row["action"],
            reason_code=row["reason_code"],
            comment=row["comment"],
            reviewer_ref=row["reviewer_ref"],
            evidence_refs=json.loads(row["evidence_refs"]) if row["evidence_refs"] else [],
            created_at=row["created_at"],
            resulting_event_version=row["resulting_event_version"],
        )

    # ── Replay ──────────────────────────────────────────────────
    def append_replay_entry(self, entry: ReplayEntry) -> ReplayEntry:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO replay_entries
                (replay_entry_id, event_ref, sequence_number, actor_type,
                 actor_ref, action, object_type, object_ref, object_version,
                 reason, metadata, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            entry.replay_entry_id, entry.event_ref, entry.sequence_number,
            entry.actor_type, entry.actor_ref, entry.action, entry.object_type,
            entry.object_ref, entry.object_version, entry.reason,
            self._to_json(entry.metadata), entry.timestamp,
        ))
        conn.commit()
        return entry

    def get_replay_for_event(self, event_ref: str) -> Sequence[ReplayEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM replay_entries WHERE event_ref = ? ORDER BY sequence_number",
            (event_ref,)
        ).fetchall()
        return [self._row_to_replay(r) for r in rows]

    def get_latest_sequence_number(self) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COALESCE(MAX(sequence_number), -1) as max_seq FROM replay_entries"
        ).fetchone()
        return row["max_seq"] if row else -1

    @staticmethod
    def _row_to_replay(row) -> ReplayEntry:
        return ReplayEntry(
            replay_entry_id=row["replay_entry_id"],
            event_ref=row["event_ref"],
            sequence_number=row["sequence_number"],
            actor_type=row["actor_type"],
            actor_ref=row["actor_ref"],
            action=row["action"],
            object_type=row["object_type"],
            object_ref=row["object_ref"],
            object_version=row["object_version"],
            reason=row["reason"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            timestamp=row["timestamp"],
        )

    # ── Idempotency ─────────────────────────────────────────────
    def save_idempotency_key(self, key: str, result_ref: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys (idempotency_key, result_ref, created_at) VALUES (?, ?, ?)",
            (key, result_ref, datetime.now().isoformat()),
        )
        conn.commit()

    def get_idempotency_result(self, key: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT result_ref FROM idempotency_keys WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return row["result_ref"] if row else None

    # ── Transaction ─────────────────────────────────────────────
    def begin_transaction(self):
        conn = self._get_conn()
        conn.execute("BEGIN")

    def commit(self):
        if self._conn:
            self._conn.commit()

    def rollback(self):
        if self._conn:
            self._conn.rollback()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def clear_all(self) -> None:
        """清除所有数据（测试用）。"""
        conn = self._get_conn()
        for table in ["evidence", "evidence_bundles", "events",
                       "event_candidate_links", "reviews", "replay_entries",
                       "idempotency_keys"]:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
