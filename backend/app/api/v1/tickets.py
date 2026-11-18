"""UC-02 endpoints: submit a sensitive request with a voice confirmation; list my tickets."""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models import AudioAssessment, AudioFile, BankAccount, ReviewCase, SupportTicket, User
from app.schemas import TicketOut
from app.services.tickets import TicketError, submit_sensitive_request

router = APIRouter(prefix="/tickets", tags=["tickets"])


def ticket_out(db: Session, t: SupportTicket) -> TicketOut:
    audio = db.execute(select(AudioFile).where(AudioFile.ticket_id == t.ticket_id).order_by(AudioFile.created_at.desc())).scalars().first()
    assessment = None
    if audio:
        assessment = db.execute(
            select(AudioAssessment).where(AudioAssessment.audio_id == audio.audio_id).order_by(AudioAssessment.assessed_at.desc())
        ).scalars().first()
    case = db.execute(select(ReviewCase).where(ReviewCase.ticket_id == t.ticket_id)).scalar_one_or_none()
    return TicketOut(
        ticket_id=t.ticket_id, reference=t.reference, request_type=t.request_type, description=t.description,
        status=t.status, created_at=t.created_at,
        assessment_status=assessment.status if assessment else None,
        spoof_score=assessment.spoof_score if assessment else None,
        case_reference=case.reference if case else None,
    )


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    account_id: uuid.UUID = Form(...),
    request_type: str = Form(...),
    description: str = Form(..., min_length=5, max_length=2000),
    related_transfer_id: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    acc = db.get(BankAccount, account_id)
    if acc is None or acc.customer_id != user.user_id:
        raise HTTPException(404, {"code": "ACCOUNT_NOT_FOUND", "message": "الحساب غير موجود"})
    data = await file.read()
    try:
        ticket, _, _ = submit_sensitive_request(
            db, customer=user, account=acc, request_type=request_type, description=description,
            audio_bytes=data, audio_filename=file.filename or "audio", related_transfer_id=related_transfer_id,
        )
    except TicketError as e:
        db.rollback()
        raise HTTPException(e.http_status, {"code": e.code, "message": str(e)}) from e
    return ticket_out(db, ticket)


@router.get("", response_model=list[TicketOut])
def my_tickets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(SupportTicket).where(SupportTicket.customer_id == user.user_id).order_by(SupportTicket.created_at.desc())).scalars().all()
    return [ticket_out(db, t) for t in rows]


@router.get("/{ticket_id}", response_model=TicketOut)
def ticket_detail(ticket_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(SupportTicket, ticket_id)
    if t is None or t.customer_id != user.user_id:
        raise HTTPException(404, {"code": "TICKET_NOT_FOUND", "message": "التذكرة غير موجودة"})
    return ticket_out(db, t)
