import secrets
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import BankAccount, Role, User, UserRole
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import settings_store as cfg
from app.services.audit import append_audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _account_number() -> str:
    return "1000" + "".join(str(secrets.randbelow(10)) for _ in range(8))


def _user_out(u: User) -> UserOut:
    return UserOut(user_id=u.user_id, full_name=u.full_name, email=u.email, status=u.status, roles=u.role_names(), created_at=u.created_at)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none():
        raise HTTPException(409, {"code": "EMAIL_TAKEN", "message": "البريد الإلكتروني مستخدم مسبقاً"})
    user = User(full_name=body.full_name.strip(), email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    role = db.execute(select(Role).where(Role.role_name == "CUSTOMER")).scalar_one_or_none()
    if role is None:
        role = Role(role_name="CUSTOMER")
        db.add(role)
        db.flush()
    db.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    # a new customer gets one SAR current account; demo balance so the flow can be tried
    db.add(BankAccount(
        customer_id=user.user_id, account_number=_account_number(), currency="SAR",
        available_balance=Decimal("10000.00"), daily_limit=cfg.get_decimal(db, "account.default_daily_limit"),
    ))
    append_audit(db, event_type="REGISTER", entity_type="USER", entity_id=user.user_id, actor_user_id=user.user_id)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.user_id, user.role_names()), roles=user.role_names())


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, {"code": "BAD_CREDENTIALS", "message": "البريد أو كلمة المرور غير صحيحة"})
    if user.status != "ACTIVE":
        raise HTTPException(403, {"code": "USER_SUSPENDED", "message": "الحساب موقوف"})
    append_audit(db, event_type="LOGIN", entity_type="USER", entity_id=user.user_id, actor_user_id=user.user_id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.user_id, user.role_names()), roles=user.role_names())


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _user_out(user)
