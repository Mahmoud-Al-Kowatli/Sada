"""UC-04 endpoints (staff only): queue, claim, evidence, decision, audio playback."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.v1.accounts import transfer_out
from app.api.v1.tickets import ticket_out
from app.core.db import get_db
from app.models import AuditLog, ReviewCase, SupportTicket, Transfer, User
from app.schemas import CaseDecisionIn, CaseDetailOut, CaseSummaryOut
from app.services.audit import append_audit
from app.services.cases import CaseError, claim_case, decide_case, evidence_bundle
from app.services.tickets import read_review_copy

router = APIRouter(prefix="/cases", tags=["cases"])
reviewer = require_roles("REVIEW_EMPLOYEE", "SYSTEM_ADMIN")


def _summary(db: Session, c: ReviewCase) -> CaseSummaryOut:
    b = evidence_bundle(db, c)
    subject = b["transfer"] or b["ticket"]
    return CaseSummaryOut(
        case_id=c.case_id, reference=c.reference, status=c.status,
        subject_type="TRANSFER" if c.transfer_id else "TICKET", subject_reference=subject.reference,
        customer_name=b["customer"].full_name if b["customer"] else "",
        triggered_rules=[r for r in c.triggered_rules.split(",") if r],
        spoof_score=b["assessment"].spoof_score if b["assessment"] else None,
        assessment_status=b["assessment"].status if b["assessment"] else None,
        assigned_reviewer_id=c.assigned_reviewer_id, created_at=c.created_at,
    )


def _get(db: Session, case_id: uuid.UUID) -> ReviewCase:
    c = db.get(ReviewCase, case_id)
    if c is None:
        raise HTTPException(404, {"code": "CASE_NOT_FOUND", "message": "الحالة غير موجودة"})
    return c


@router.get("", response_model=list[CaseSummaryOut])
def queue(status: str | None = None, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    stmt = select(ReviewCase).order_by(ReviewCase.created_at.desc())
    if status:
        stmt = stmt.where(ReviewCase.status == status)
    return [_summary(db, c) for c in db.execute(stmt).scalars().all()]


@router.post("/{case_id}/claim", response_model=CaseSummaryOut)
def claim(case_id: uuid.UUID, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    c = _get(db, case_id)
    try:
        claim_case(db, c, user)
    except CaseError as e:
        raise HTTPException(e.http_status, {"code": e.code, "message": str(e)}) from e
    return _summary(db, c)


@router.get("/{case_id}", response_model=CaseDetailOut)
def detail(case_id: uuid.UUID, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    c = _get(db, case_id)
    b = evidence_bundle(db, c)
    s = _summary(db, c)
    a = b["assessment"]
    timeline = [
        {"at": row.created_at, "event": row.event_type, "actor": (db.get(User, row.actor_user_id).full_name if row.actor_user_id else "النظام"), "details": row.event_details}
        for row in db.execute(
            select(AuditLog).where(AuditLog.entity_id.in_([x for x in [c.case_id, c.transfer_id, c.ticket_id] if x])).order_by(AuditLog.created_at)
        ).scalars()
    ]
    return CaseDetailOut(
        **s.model_dump(),
        customer_email=b["customer"].email if b["customer"] else "",
        account_number=b["account"].account_number if b["account"] else "",
        available_balance=b["account"].available_balance if b["account"] else 0,
        frozen_balance=b["account"].frozen_balance if b["account"] else 0,
        transfer=transfer_out(db, b["transfer"]) if b["transfer"] else None,
        ticket=ticket_out(db, b["ticket"]) if b["ticket"] else None,
        assessment={
            "status": a.status, "spoof_score": str(a.spoof_score) if a.spoof_score is not None else None,
            "threshold": str(a.threshold) if a.threshold is not None else None, "quality_status": a.quality_status,
            "model_version": a.model_version, "processing_time_ms": a.processing_time_ms, "assessed_at": a.assessed_at.isoformat(),
        } if a else None,
        audio_available=bool(b["audio"] and b["audio"].review_copy_status == "RETAINED"),
        decision=c.decision, decision_rationale=c.decision_rationale, reviewed_at=c.reviewed_at, timeline=timeline,
    )


@router.get("/{case_id}/audio")
def audio(case_id: uuid.UUID, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    """Authorized playback of the retained copy: streamed through the API, never a direct link."""
    c = _get(db, case_id)
    b = evidence_bundle(db, c)
    a = b["audio"]
    if a is None or a.review_copy_status != "RETAINED":
        raise HTTPException(404, {"code": "AUDIO_UNAVAILABLE", "message": "التسجيل غير متاح"})
    append_audit(db, event_type="PLAY_AUDIO", entity_type="REVIEW_CASE", entity_id=c.case_id, actor_user_id=user.user_id)
    db.commit()
    media = "audio/wav" if a.file_format == "wav" else "audio/flac"
    return Response(read_review_copy(a.storage_reference), media_type=media)


@router.post("/{case_id}/decision", response_model=CaseSummaryOut)
def decide(case_id: uuid.UUID, body: CaseDecisionIn, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    c = _get(db, case_id)
    try:
        decide_case(db, c, user, body.decision, body.rationale)
    except CaseError as e:
        raise HTTPException(e.http_status, {"code": e.code, "message": str(e)}) from e
    return _summary(db, c)
