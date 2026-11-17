"""UC-01 Execute Internal Transfer, exactly as in the sequence diagram:

validate session (API layer) -> verify OTP -> account status / balance / daily limit
-> Risk Engine -> either HOLD + REVIEW_CASE (202) or atomic execution via the Ledger Service (200).

Everything after OTP happens in ONE database transaction owned by this service."""
import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BankAccount, ReviewCase, Transfer, User
from app.services import ledger
from app.services.audit import append_audit
from app.services.references import next_reference
from app.services.risk import evaluate_transfer


class TransferError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 422):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass
class TransferOutcome:
    transfer: Transfer
    status: str  # COMPLETED | HELD
    triggered_rules: list[str]
    case: ReviewCase | None = None


def _today_total(db: Session, source_account_id: uuid.UUID) -> Decimal:
    start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total = db.scalar(
        select(func.coalesce(func.sum(Transfer.amount), 0)).where(
            Transfer.source_account_id == source_account_id,
            Transfer.created_at >= start,
            Transfer.status.in_(("COMPLETED", "HELD")),
        )
    )
    return Decimal(total or 0)


def precheck(db: Session, *, source: BankAccount, destination_number: str, amount: Decimal) -> BankAccount:
    """Advisory checks that give the customer a fast, specific error (422). The authoritative
    balance check happens again under lock inside the ledger."""
    if amount <= 0:
        raise TransferError("INVALID_AMOUNT", "المبلغ يجب أن يكون أكبر من صفر")
    dest = db.execute(select(BankAccount).where(BankAccount.account_number == destination_number)).scalar_one_or_none()
    if dest is None:
        raise TransferError("DESTINATION_NOT_FOUND", "رقم حساب المستفيد غير موجود", 404)
    if dest.account_id == source.account_id:
        raise TransferError("SAME_ACCOUNT", "لا يمكن التحويل إلى الحساب نفسه")
    if dest.currency != source.currency:
        raise TransferError("CURRENCY_MISMATCH", "عملة الحساب المستفيد مختلفة")
    if source.status != "ACTIVE":
        raise TransferError("ACCOUNT_INACTIVE", "الحساب غير نشط")
    if dest.status != "ACTIVE":
        raise TransferError("DESTINATION_INACTIVE", "حساب المستفيد غير نشط")
    if source.available_balance < amount:
        raise TransferError("INSUFFICIENT_BALANCE", "الرصيد المتاح غير كافٍ")
    if _today_total(db, source.account_id) + amount > source.daily_limit:
        raise TransferError("DAILY_LIMIT_EXCEEDED", "تجاوزت الحد اليومي للتحويل")
    return dest


def execute_transfer(
    db: Session,
    *,
    customer: User,
    source: BankAccount,
    destination: BankAccount,
    amount: Decimal,
    note: str | None,
) -> TransferOutcome:
    risk = evaluate_transfer(
        db,
        source_account_id=source.account_id,
        destination_account_id=destination.account_id,
        amount=amount,
        initiated_by=customer.user_id,
    )
    reference = next_reference(db, "TRF")

    if risk.manual_review:
        # BEGIN -> lock + recheck -> freeze -> HELD transfer -> REVIEW_CASE -> audit -> COMMIT
        try:
            ledger.hold_amount(db, source.account_id, amount)
        except ledger.LedgerError as e:
            raise TransferError(e.code, str(e)) from e
        transfer = Transfer(
            reference=reference,
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            initiated_by=customer.user_id,
            amount=amount,
            note=note,
            status="HELD",
        )
        db.add(transfer)
        db.flush()
        case = ReviewCase(
            reference=next_reference(db, "REV"),
            transfer_id=transfer.transfer_id,
            status="OPEN",
            triggered_rules=",".join(risk.triggered_rules),
        )
        db.add(case)
        db.flush()
        append_audit(
            db,
            event_type="CREATE_HOLD",
            entity_type="TRANSFER",
            entity_id=transfer.transfer_id,
            actor_user_id=customer.user_id,
            details={"reference": reference, "amount": str(amount), "rules": risk.triggered_rules, "case": case.reference},
        )
        db.commit()
        return TransferOutcome(transfer, "HELD", risk.triggered_rules, case)

    # Risk passed: atomic execution through the ledger service
    transfer = Transfer(
        reference=reference,
        source_account_id=source.account_id,
        destination_account_id=destination.account_id,
        initiated_by=customer.user_id,
        amount=amount,
        note=note,
        status="COMPLETED",
        completed_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(transfer)
    db.flush()
    try:
        ledger.post_transaction(
            db,
            transaction_type="TRANSFER",
            transfer_id=transfer.transfer_id,
            entries=[(source.account_id, "DEBIT", amount), (destination.account_id, "CREDIT", amount)],
        )
    except ledger.LedgerError as e:
        db.rollback()
        raise TransferError(e.code, str(e)) from e
    append_audit(
        db,
        event_type="POST_LEDGER",
        entity_type="TRANSFER",
        entity_id=transfer.transfer_id,
        actor_user_id=customer.user_id,
        details={"reference": reference, "amount": str(amount)},
    )
    db.commit()
    return TransferOutcome(transfer, "COMPLETED", risk.triggered_rules)


def settle_held_transfer(db: Session, transfer: Transfer, reviewer_id: uuid.UUID) -> None:
    """UC-04 accept: money leaves the frozen balance and lands in the destination."""
    if transfer.status != "HELD":
        raise TransferError("NOT_HELD", "التحويل ليس بحالة معلّق")
    ledger.post_transaction(
        db,
        transaction_type="TRANSFER",
        transfer_id=transfer.transfer_id,
        from_frozen=True,
        entries=[
            (transfer.source_account_id, "DEBIT", transfer.amount),
            (transfer.destination_account_id, "CREDIT", transfer.amount),
        ],
    )
    transfer.status = "COMPLETED"
    transfer.completed_at = dt.datetime.now(dt.timezone.utc)
    append_audit(
        db, event_type="RELEASE_HOLD", entity_type="TRANSFER", entity_id=transfer.transfer_id,
        actor_user_id=reviewer_id, details={"reference": transfer.reference, "amount": str(transfer.amount)},
    )


def cancel_held_transfer(db: Session, transfer: Transfer, reviewer_id: uuid.UUID) -> None:
    """UC-04 reject: the frozen amount goes back to the customer's available balance."""
    if transfer.status != "HELD":
        raise TransferError("NOT_HELD", "التحويل ليس بحالة معلّق")
    ledger.release_hold(db, transfer.source_account_id, transfer.amount)
    transfer.status = "CANCELLED"
    append_audit(
        db, event_type="CANCEL_HOLD", entity_type="TRANSFER", entity_id=transfer.transfer_id,
        actor_user_id=reviewer_id, details={"reference": transfer.reference, "amount": str(transfer.amount)},
    )
