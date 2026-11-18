"""System administration: settings, users/roles, audit log, ledger view and reversal."""
import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models import AuditLog, LedgerTransaction, ReviewCase, Role, Transfer, User, UserRole
from app.schemas import AuditOut, SettingsOut, SettingUpdateIn
from app.services import ledger
from app.services import settings_store as cfg
from app.services.audit import append_audit

router = APIRouter(prefix="/admin", tags=["admin"])
admin = require_roles("SYSTEM_ADMIN")
staff = require_roles("SYSTEM_ADMIN", "REVIEW_EMPLOYEE")


@router.get("/settings", response_model=SettingsOut)
def get_settings_(user: User = Depends(staff), db: Session = Depends(get_db)):
    out = cfg.all_settings(db)
    db.commit()
    return SettingsOut(settings=out)


@router.put("/settings", response_model=SettingsOut)
def update_setting(body: SettingUpdateIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    try:
        cfg.set_setting(db, body.key, body.value, user.user_id)
    except KeyError:
        raise HTTPException(404, {"code": "UNKNOWN_SETTING", "message": "الإعداد غير معروف"})
    db.commit()
    return SettingsOut(settings=cfg.all_settings(db))


@router.get("/stats")
def stats(user: User = Depends(staff), db: Session = Depends(get_db)):
    start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    def count(model, *conds):
        return db.scalar(select(func.count()).select_from(model).where(*conds)) or 0
    return {
        "open_cases": count(ReviewCase, ReviewCase.status == "OPEN"),
        "in_review": count(ReviewCase, ReviewCase.status == "IN_REVIEW"),
        "accepted_today": count(ReviewCase, ReviewCase.status == "ACCEPTED", ReviewCase.reviewed_at >= start),
        "rejected_today": count(ReviewCase, ReviewCase.status == "REJECTED", ReviewCase.reviewed_at >= start),
        "completed_today": count(Transfer, Transfer.status == "COMPLETED", Transfer.created_at >= start),
        "held_today": count(Transfer, Transfer.status == "HELD", Transfer.created_at >= start),
    }


@router.get("/users")
def users(user: User = Depends(admin), db: Session = Depends(get_db)):
    return [
        {"user_id": u.user_id, "full_name": u.full_name, "email": u.email, "status": u.status, "roles": u.role_names()}
        for u in db.execute(select(User).order_by(User.created_at)).scalars()
    ]


@router.put("/users/{user_id}/roles")
def set_roles(user_id: uuid.UUID, roles: list[str], user: User = Depends(admin), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, {"code": "USER_NOT_FOUND", "message": "المستخدم غير موجود"})
    for ur in db.execute(select(UserRole).where(UserRole.user_id == user_id)).scalars():
        db.delete(ur)
    for name in roles:
        role = db.execute(select(Role).where(Role.role_name == name)).scalar_one_or_none()
        if role is None:
            raise HTTPException(422, {"code": "UNKNOWN_ROLE", "message": f"الدور {name} غير معروف"})
        db.add(UserRole(user_id=user_id, role_id=role.role_id))
    append_audit(db, event_type="UPDATE_ROLES", entity_type="USER", entity_id=user_id, actor_user_id=user.user_id, details={"roles": roles})
    db.commit()
    db.refresh(target)
    return {"user_id": target.user_id, "roles": target.role_names()}


@router.get("/audit", response_model=list[AuditOut])
def audit(limit: int = 100, user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))).scalars().all()
    return [
        AuditOut(
            audit_id=r.audit_id, actor_name=(db.get(User, r.actor_user_id).full_name if r.actor_user_id else None),
            event_type=r.event_type, entity_type=r.entity_type, entity_id=r.entity_id, event_details=r.event_details, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/ledger")
def ledger_view(limit: int = 100, user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.execute(select(LedgerTransaction).order_by(LedgerTransaction.created_at.desc()).limit(min(limit, 500))).scalars().all()
    return [
        {
            "ledger_tx_id": t.ledger_tx_id, "transaction_type": t.transaction_type, "status": t.status,
            "transfer_id": t.transfer_id, "reversal_of_id": t.reversal_of_id, "posted_at": t.posted_at,
            "entries": [{"account_id": e.account_id, "entry_type": e.entry_type, "amount": str(e.amount)} for e in t.entries],
        }
        for t in rows
    ]


@router.post("/ledger/{ledger_tx_id}/reverse")
def reverse(ledger_tx_id: uuid.UUID, user: User = Depends(admin), db: Session = Depends(get_db)):
    try:
        tx = ledger.reverse_transaction(db, ledger_tx_id)
    except ledger.LedgerError as e:
        db.rollback()
        raise HTTPException(409, {"code": e.code, "message": str(e)}) from e
    append_audit(db, event_type="REVERSE_LEDGER", entity_type="LEDGER_TRANSACTION", entity_id=tx.ledger_tx_id, actor_user_id=user.user_id, details={"reversal_of": str(ledger_tx_id)})
    db.commit()
    return {"ledger_tx_id": tx.ledger_tx_id, "reversal_of_id": tx.reversal_of_id}
