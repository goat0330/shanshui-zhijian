"""
SQLite 数据库模型 — 产品链持久化
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, create_engine
from sqlalchemy.orm import sessionmaker

from core.event_governance.persistence import Base


class AlertRecord(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(64), unique=True, nullable=False, index=True)
    detection_id = Column(String(64), default="")
    status = Column(String(20), default="pending")  # pending/confirmed/rejected
    category = Column(String(64), default="candidate")
    confidence = Column(Float, default=0.0)
    geometry = Column(Text, default="")  # GeoJSON string
    evidence_refs = Column(Text, default="")  # JSON list
    created_at = Column(String(32), default=lambda: datetime.now().isoformat())
    reviewed_at = Column(String(32), default="")
    reviewed_by = Column(String(64), default="")
    reject_reason = Column(String(256), default="")


class EventRecord(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    alert_id = Column(String(64), default="")
    title = Column(String(256), default="")
    status = Column(String(20), default="open")
    created_at = Column(String(32), default=lambda: datetime.now().isoformat())
    closed_at = Column(String(32), default="")
    notes = Column(Text, default="")


class WorkOrderRecord(Base):
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, nullable=False, index=True)
    event_id = Column(String(64), default="")
    assignee = Column(String(64), default="")
    status = Column(String(20), default="pending")
    created_at = Column(String(32), default=lambda: datetime.now().isoformat())
    completed_at = Column(String(32), default="")
    feedback = Column(Text, default="")


def init_db(db_path: str = "shanshui.db"):
    """初始化数据库，创建表"""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal
