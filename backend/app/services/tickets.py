"""UC-02 Submit Sensitive Support Request.

Order of operations mirrors the activity diagram:
validate audio -> create ticket + audio metadata -> store encrypted retained copy ->
request AI assessment -> Risk Engine (with or without the AI result) -> case or SUBMITTED ->
audit -> return reference and status.
"""
import datetime as dt
import hashlib
import os
import struct
import uuid
from decimal import Decimal

from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AudioAssessment, AudioFile, BankAccount, ReviewCase, SupportTicket, User
from app.services import ai_client
from app.services import settings_store as cfg
from app.services.audit import append_audit
from app.services.references import next_reference
from app.services.risk import evaluate_sensitive_request

REQUEST_TYPES = {"RAISE_LIMIT", "RELEASE_HELD", "UPDATE_CONTACT"}


class TicketError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


# ----------------------------------------------------------- audio checks ---
def sniff_format(data: bytes) -> str | None:
    """Return 'wav' / 'flac' from the file header, or None. The extension is not trusted."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if len(data) >= 4 and data[:4] == b"fLaC":
        return "flac"
    return None


def wav_duration_seconds(data: bytes) -> Decimal | None:
    """Cheap duration estimate from the WAV header (fmt + data chunk sizes)."""
    try:
        pos = 12
        sample_rate = channels = bits = None
        while pos + 8 <= len(data):
            cid = data[pos : pos + 4]
            size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
            if cid == b"fmt ":
                channels, sample_rate = struct.unpack("<HI", data[pos + 10 : pos + 16])
                bits = struct.unpack("<H", data[pos + 22 : pos + 24])[0]
            elif cid == b"data" and sample_rate and channels and bits:
                bytes_per_sec = sample_rate * channels * bits // 8
                return Decimal(size / bytes_per_sec).quantize(Decimal("0.01"))
            pos += 8 + size + (size % 2)
    except Exception:
        return None
    return None


def validate_audio(data: bytes, filename: str) -> str:
    s = get_settings()
    if not data:
        raise TicketError("EMPTY_FILE", "الملف فارغ")
    if len(data) > s.audio_max_bytes:
        raise TicketError("FILE_TOO_LARGE", f"حجم الملف يتجاوز {s.audio_max_bytes // (1024*1024)} MB")
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    fmt = sniff_format(data)
    if fmt is None or ext not in s.audio_allowed_formats or fmt != ext:
        raise TicketError("UNSUPPORTED_FORMAT", "لم يُرفق ملف صالح: الصيغة غير مدعومة، اختر WAV أو FLAC")
    return fmt


# --------------------------------------------------------- evidence store ---
def _fernet() -> Fernet:
    s = get_settings()
    key = hashlib.sha256(s.jwt_secret.encode()).digest()
    import base64

    return Fernet(base64.urlsafe_b64encode(key))


def store_review_copy(data: bytes, audio_id: uuid.UUID, fmt: str) -> str:
    s = get_settings()
    os.makedirs(s.evidence_dir, exist_ok=True)
    path = os.path.join(s.evidence_dir, f"{audio_id}.{fmt}.enc")
    with open(path, "wb") as f:
        f.write(_fernet().encrypt(data))
    return path


def read_review_copy(path: str) -> bytes:
    with open(path, "rb") as f:
        return _fernet().decrypt(f.read())


def delete_review_copy(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


# --------------------------------------------------------------- use case ---
def submit_sensitive_request(
    db: Session,
    *,
    customer: User,
    account: BankAccount,
    request_type: str,
    description: str,
    audio_bytes: bytes,
    audio_filename: str,
    related_transfer_id: uuid.UUID | None = None,
) -> tuple[SupportTicket, AudioAssessment, ReviewCase | None]:
    if request_type not in REQUEST_TYPES:
        raise TicketError("INVALID_REQUEST_TYPE", "نوع الطلب غير معروف")
    fmt = validate_audio(audio_bytes, audio_filename)

    ticket = SupportTicket(
        reference=next_reference(db, "TKT"),
        customer_id=customer.user_id,
        account_id=account.account_id,
        related_transfer_id=related_transfer_id,
        request_type=request_type,
        description=description,
        status="SUBMITTED",
    )
    db.add(ticket)
    db.flush()

    retention_days = cfg.get_int(db, "audio.retention_days")
    audio = AudioFile(
        ticket_id=ticket.ticket_id,
        storage_reference="",
        file_format=fmt,
        file_size_bytes=len(audio_bytes),
        duration_seconds=wav_duration_seconds(audio_bytes) if fmt == "wav" else None,
        retention_expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=retention_days),
    )
    db.add(audio)
    db.flush()
    audio.storage_reference = store_review_copy(audio_bytes, audio.audio_id, fmt)

    ai = ai_client.assess_audio(audio_bytes, audio_filename, ticket.reference)
    assessment = AudioAssessment(
        audio_id=audio.audio_id,
        status=ai.status,
        spoof_score=ai.spoof_score,
        threshold=ai.threshold,
        quality_status=ai.quality_status,
        model_version=ai.model_version,
        processing_time_ms=ai.processing_time_ms,
    )
    db.add(assessment)
    db.flush()

    open_cases = db.scalar(
        select(func.count()).select_from(ReviewCase).join(SupportTicket, ReviewCase.ticket_id == SupportTicket.ticket_id)
        .where(SupportTicket.customer_id == customer.user_id, ReviewCase.status.in_(("OPEN", "IN_REVIEW")))
    ) or 0
    risk = evaluate_sensitive_request(
        db,
        request_type=request_type,
        spoof_score=ai.spoof_score,
        assessment_status=ai.status,
        open_cases_for_customer=open_cases,
    )

    case = None
    if risk.manual_review:
        ticket.status = "PENDING_REVIEW"
        case = ReviewCase(
            reference=next_reference(db, "REV"),
            ticket_id=ticket.ticket_id,
            status="OPEN",
            triggered_rules=",".join(risk.triggered_rules),
        )
        db.add(case)
        db.flush()

    append_audit(
        db,
        event_type="SUBMIT_SENSITIVE_REQUEST",
        entity_type="SUPPORT_TICKET",
        entity_id=ticket.ticket_id,
        actor_user_id=customer.user_id,
        details={
            "reference": ticket.reference,
            "request_type": request_type,
            "assessment": ai.status,
            "spoof_score": str(ai.spoof_score) if ai.spoof_score is not None else None,
            "rules": risk.triggered_rules,
            "case": case.reference if case else None,
        },
    )
    db.commit()
    return ticket, assessment, case
