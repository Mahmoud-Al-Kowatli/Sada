"""UC-01 endpoints.

POST /transfers/precheck  -> validates the request, issues the OTP challenge (step 1 of the UI)
POST /transfers           -> verifies the OTP and executes: 200 COMPLETED or 202 HELD (pending review)
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.v1.accounts import transfer_out
from app.core.db import get_db
from app.models import BankAccount, User
from app.schemas import TransferExecuteIn, TransferOut, TransferPrecheckIn, TransferPrecheckOut
from app.services import otp as otp_service
from app.services.transfers import TransferError, execute_transfer, precheck

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _own_account(db: Session, user: User, account_id) -> BankAccount:
    acc = db.get(BankAccount, account_id)
    if acc is None or acc.customer_id != user.user_id:
        raise HTTPException(404, {"code": "ACCOUNT_NOT_FOUND", "message": "الحساب غير موجود"})
    return acc


@router.post("/precheck", response_model=TransferPrecheckOut)
def transfer_precheck(body: TransferPrecheckIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    source = _own_account(db, user, body.source_account_id)
    try:
        dest = precheck(db, source=source, destination_number=body.destination_account_number, amount=body.amount)
    except TransferError as e:
        raise HTTPException(e.http_status, {"code": e.code, "message": str(e)}) from e
    challenge, dev_code = otp_service.issue_otp(db, user.user_id, "TRANSFER")
    db.commit()
    owner = db.get(User, dest.customer_id)
    return TransferPrecheckOut(ok=True, destination_name=owner.full_name if owner else "", otp_id=challenge.otp_id, dev_otp_code=dev_code)


@router.post("", response_model=TransferOut)
def transfer_execute(body: TransferExecuteIn, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    source = _own_account(db, user, body.source_account_id)
    if not otp_service.verify_otp(db, user.user_id, body.otp_id, body.otp_code):
        db.commit()
        raise HTTPException(401, {"code": "INVALID_OTP", "message": "رمز التحقق غير صحيح أو منتهي الصلاحية"})
    try:
        dest = precheck(db, source=source, destination_number=body.destination_account_number, amount=body.amount)
        outcome = execute_transfer(db, customer=user, source=source, destination=dest, amount=body.amount, note=body.note)
    except TransferError as e:
        db.rollback()
        raise HTTPException(e.http_status, {"code": e.code, "message": str(e)}) from e
    response.status_code = 202 if outcome.status == "HELD" else 200
    return transfer_out(db, outcome.transfer)
