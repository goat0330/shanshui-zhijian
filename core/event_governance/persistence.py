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
    decision = Column(String(20), default="")
    reason = Column(Text, default="")
    version_at_review = Column(Integer, nullable=False)
    reviewed_at = Column(String(32), default=lambda: datetime.now().isoformat())


class GovernedEventRecord(Base):
    __tablename__ = "governance_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), nullable=False, index=True)
    version = Column(String(8), nullable=False)
    candidate_id = Column(String(128), nullable=False)
    event_type = Column(String(64), default="")
    payload = Column(Text, default="{}")
    created_at = Column(String(32), default=lambda: datetime.now().isoformat())


class ReplayRecordDB(Base):
    __tablename__ = "governance_replays"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), unique=True, nullable=False, index=True)
    replay_id = Column(String(128), unique=True, nullable=False)
    replayed_at = Column(String(32), default=lambda: datetime.now().isoformat())
    result = Column(String(32), default="ok")


def create_session(db_path: str = ":memory:"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
