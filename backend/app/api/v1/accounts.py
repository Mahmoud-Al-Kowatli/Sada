import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models import BankAccount, ReviewCase, Transfer, User
from app.schemas import AccountOut, TransferOut
from app.services.transfers import _today_total

router = APIRouter(prefix="/accounts", tags=["accounts"])


def account_out(db: Session, a: BankAccount) -> AccountOut:
    return AccountOut(
        account_id=a.account_id, account_number=a.account_number, currency=a.currency,
        available_balance=a.available_balance, frozen_balance=a.frozen_balance, daily_limit=a.daily_limit,
        daily_used=_today_total(db, a.account_id), status=a.status,
    )


def transfer_out(db: Session, t: Transfer) -> TransferOut:
    dest = db.get(BankAccount, t.destination_account_id)
    dest_user = db.get(User, dest.customer_id) if dest else None
    case = db.execute(select(ReviewCase).where(ReviewCase.transfer_id == t.transfer_id)).scalar_one_or_none()
    return TransferOut(
        transfer_id=t.transfer_id, reference=t.reference, amount=t.amount, status=t.status,
        destination_account_number=dest.account_number if dest else "", destination_name=dest_user.full_name if dest_user else None,
        note=t.note, created_at=t.created_at, completed_at=t.completed_at,
        triggered_rules=case.triggered_rules.split(",") if case and case.triggered_rules else [],
        case_reference=case.reference if case else None,
    )


@router.get("", response_model=list[AccountOut])
def my_accounts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [account_out(db, a) for a in user.accounts]


@router.get("/{account_id}/transfers", response_model=list[TransferOut])
def account_transfers(account_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acc = db.get(BankAccount, account_id)
    if acc is None or acc.customer_id != user.user_id:
        raise HTTPException(404, {"code": "ACCOUNT_NOT_FOUND", "message": "الحساب غير موجود"})
    rows = db.execute(
        select(Transfer).where(or_(Transfer.source_account_id == account_id, Transfer.destination_account_id == account_id))
        .order_by(Transfer.created_at.desc()).limit(50)
    ).scalars().all()
    return [transfer_out(db, t) for t in rows]


@router.get("/lookup/{account_number}")
def lookup(account_number: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Beneficiary name confirmation shown while typing the destination (UI: 'تم التحقق من الحساب')."""
    acc = db.execute(select(BankAccount).where(BankAccount.account_number == account_number)).scalar_one_or_none()
    if acc is None:
        raise HTTPException(404, {"code": "DESTINATION_NOT_FOUND", "message": "رقم حساب المستفيد غير موجود"})
    owner = db.get(User, acc.customer_id)
    return {"account_number": acc.account_number, "display_name": owner.full_name if owner else "", "currency": acc.currency}
