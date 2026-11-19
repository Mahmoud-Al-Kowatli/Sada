"""Assessment Database (the AI service keeps its own store; the platform links by assessment_id)."""
import datetime as dt
import json
import uuid

from sqlalchemy import DateTime, Float, Integer, String, Text, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Assessment(Base):
    __tablename__ = "assessment"

    assessment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(30))  # COMPLETED | INSUFFICIENT_QUALITY | INVALID_AUDIO
    spoof_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_window_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_window_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30))
    quality_json: Mapped[str] = mapped_column(Text, default="{}")
    window_scores_json: Mapped[str] = mapped_column(Text, default="[]")
    model_version: Mapped[str] = mapped_column(String(80))
    preprocess_version: Mapped[str] = mapped_column(String(40), default="pp-1.0")
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    assessed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


_engine = None
_Session = None


def init() -> None:
    global _engine, _Session
    s = get_settings()
    import os

    if s.assessments_db.startswith("sqlite:///"):
        os.makedirs(os.path.dirname(s.assessments_db.replace("sqlite:///", "")) or ".", exist_ok=True)
    _engine = create_engine(s.assessments_db, connect_args={"check_same_thread": False} if "sqlite" in s.assessments_db else {})
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


def session() -> Session:
    if _Session is None:
        init()
    return _Session()


def save(a: Assessment) -> Assessment:
    with session() as db:
        db.add(a)
        db.commit()
        return a


def to_dict(a: Assessment) -> dict:
    return {
        "assessment_id": str(a.assessment_id), "reference": a.reference, "status": a.status,
        "spoof_score": a.spoof_score, "max_window_score": a.max_window_score, "max_window_index": a.max_window_index,
        "threshold": a.threshold, "quality_status": a.quality_status, "quality": json.loads(a.quality_json),
        "window_scores": json.loads(a.window_scores_json), "model_version": a.model_version,
        "preprocess_version": a.preprocess_version, "processing_time_ms": a.processing_time_ms,
        "assessed_at": a.assessed_at.isoformat(),
    }
