from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()


class CandidateRecord(Base):
    __tablename__ = "governance_candidates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(128), unique=True, nullable=False, index=True)
    source = Column(String(64), default="")
    payload = Column(Text, default="{}")
    ingested_at = Column(String(32), default=lambda: datetime.now().isoformat())


class EvidenceBundleRecord(Base):
    __tablename__ = "governance_evidence_bundles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bundle_id = Column(String(128), unique=True, nullable=False, index=True)
    candidate_id = Column(String(128), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    items = Column(Text, default="[]")
    status = Column(String(20), default="draft")
    created_at = Column(String(32), default=lambda: datetime.now().isoformat())


class ReviewRecord(Base):
    __tablename__ = "governance_reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String(128), unique=True, nullable=False, index=True)
    bundle_id = Column(String(128), nullable=False, index=True)
    reviewer = Column(String(64), default="")
    decision = Column(String(30), default="")
    reason = Column(Text, default="")
    version_at_review = Column(Integer, nullable=False)
    reviewed_at = Column(String(32), default=lambda: datetime.now().isoformat())
    # new fields for reclassify and review meta
    category = Column(String(64), nullable=True, default=None)
    comment = Column(Text, default="")
    candidate_id = Column(String(128), nullable=True, default=None)


class GovernedEventRecord(Base):
    __tablename__ = "governance_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    candidate_id = Column(String(128), nullable=False)
    event_type = Column(String(64), default="")
    payload = Column(Text, default="{}")
    status = Column(String(30), default="under_review")
    created_at = Column(String(32), default=lambda: datetime.now().isoformat())
    updated_at = Column(String(32), nullable=True, default=None)


class ReplayRecordDB(Base):
    __tablename__ = "governance_replays"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), nullable=False, index=True)
    replay_id = Column(String(128), unique=True, nullable=False)
    sequence_number = Column(Integer, default=0, nullable=False)
    actor_type = Column(String(20), default="system")
    actor_ref = Column(String(64), default="")
    action = Column(String(64), default="")
    object_type = Column(String(32), default="event")
    object_ref = Column(String(128), default="")
    details = Column(Text, default="")
    replayed_at = Column(String(32), default=lambda: datetime.now().isoformat())


def create_session(db_path: str = ":memory:"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
