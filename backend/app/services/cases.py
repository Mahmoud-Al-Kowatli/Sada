"""UC-04 Review Suspicious Case: claim -> evidence -> human decision -> atomic settlement."""
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AudioAssessment, AudioFile, BankAccount, ReviewCase, SupportTicket, Transfer, User
from app.services import ledger
from app.services.audit import append_audit
from app.services.tickets import delete_review_copy
from app.services.transfers import TransferError, cancel_held_transfer, settle_held_transfer


class CaseError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 409):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def claim_case(db: Session, case: ReviewCase, reviewer: User) -> ReviewCase:
    if case.status == "OPEN":
        case.status = "IN_REVIEW"
        case.assigned_reviewer_id = reviewer.user_id
    elif case.status == "IN_REVIEW" and case.assigned_reviewer_id != reviewer.user_id:
        raise CaseError("CLAIMED_BY_OTHER", "الحالة مستلمة من مراجع آخر")
    elif case.status not in ("OPEN", "IN_REVIEW"):
        raise CaseError("CASE_CLOSED", "الحالة مغلقة")
    append_audit(
        db, event_type="CLAIM_CASE", entity_type="REVIEW_CASE", entity_id=case.case_id,
        actor_user_id=reviewer.user_id, details={"reference": case.reference},
    )
    db.commit()
    return case


def evidence_bundle(db: Session, case: ReviewCase) -> dict:
    """Everything the reviewer screen shows in one place."""
    out: dict = {"case": case, "transfer": None, "ticket": None, "audio": None, "assessment": None, "customer": None, "account": None}
    if case.transfer_id:
        t = db.get(Transfer, case.transfer_id)
        out["transfer"] = t
        out["account"] = db.get(BankAccount, t.source_account_id)
        out["customer"] = db.get(User, t.initiated_by)
    if case.ticket_id:
        tk = db.get(SupportTicket, case.ticket_id)
        out["ticket"] = tk
        out["account"] = db.get(BankAccount, tk.account_id)
        out["customer"] = db.get(User, tk.customer_id)
        audio = db.execute(select(AudioFile).where(AudioFile.ticket_id == tk.ticket_id).order_by(AudioFile.created_at.desc())).scalars().first()
        out["audio"] = audio
        if audio:
            out["assessment"] = db.execute(
                select(AudioAssessment).where(AudioAssessment.audio_id == audio.audio_id).order_by(AudioAssessment.assessed_at.desc())
            ).scalars().first()
    return out


def decide_case(db: Session, case: ReviewCase, reviewer: User, decision: str, rationale: str) -> ReviewCase:
    if decision not in ("ACCEPTED", "REJECTED"):
        raise CaseError("INVALID_DECISION", "القرار يجب أن يكون قبول أو رفض", 422)
    if not rationale or len(rationale.strip()) < 5:
        raise CaseError("RATIONALE_REQUIRED", "سبب القرار إلزامي", 422)
    if case.status != "IN_REVIEW" or case.assigned_reviewer_id != reviewer.user_id:
        raise CaseError("NOT_CLAIMED", "يجب استلام الحالة قبل اتخاذ القرار")

    try:
        # --- one atomic transaction: case + money + ticket + audit ---
        case.status = decision
        case.decision = decision
        case.decision_rationale = rationale.strip()
        case.reviewed_at = dt.datetime.now(dt.timezone.utc)

        if case.transfer_id:
            transfer = db.get(Transfer, case.transfer_id)
            if decision == "ACCEPTED":
                settle_held_transfer(db, transfer, reviewer.user_id)
            else:
                cancel_held_transfer(db, transfer, reviewer.user_id)

        if case.ticket_id:
            ticket = db.get(SupportTicket, case.ticket_id)
            ticket.status = "APPROVED" if decision == "ACCEPTED" else "REJECTED"
            # retention policy: the retained copy is deleted once the human decision is recorded
            for audio in db.execute(select(AudioFile).where(AudioFile.ticket_id == ticket.ticket_id)).scalars():
                if audio.review_copy_status == "RETAINED":
                    delete_review_copy(audio.storage_reference)
                    audio.review_copy_status = "DELETED"
                    audio.deleted_at = dt.datetime.now(dt.timezone.utc)

        append_audit(
            db, event_type=f"CASE_{decision}", entity_type="REVIEW_CASE", entity_id=case.case_id,
            actor_user_id=reviewer.user_id, details={"reference": case.reference, "rationale": rationale.strip()},
        )
        db.commit()
    except (ledger.LedgerError, TransferError) as e:
        db.rollback()
        raise CaseError(getattr(e, "code", "SETTLEMENT_FAILED"), str(e), 409) from e
    return case
