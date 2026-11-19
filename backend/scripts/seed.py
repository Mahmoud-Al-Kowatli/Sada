"""Seed demo data matching the UI mock-ups.

    python -m scripts.seed

Creates roles, three users (customer / reviewer / admin), accounts with the balances shown in
the designs, a destination customer (نورة العتيبي) and the default settings.
Safe to run twice: existing users are left as they are.
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import BankAccount, Role, User, UserRole
from app.services import settings_store as cfg

ROLES = ["CUSTOMER", "REVIEW_EMPLOYEE", "SYSTEM_ADMIN"]

USERS = [
    # name, email, password, roles, account_number, available, frozen
    ("أحمد محمد المنصوري", "ahmad.mansouri@example.com", "Customer#2026", ["CUSTOMER"], "100029485612", "24850.00", "5000.00"),
    ("نورة العتيبي", "noura.otaibi@example.com", "Customer#2026", ["CUSTOMER"], "100058329017", "12400.00", "0.00"),
    ("خالد السالم", "khaled.salem@example.com", "Customer#2026", ["CUSTOMER"], "100071234455", "3200.00", "0.00"),
    ("مريم القحطاني", "maryam.review@sada.example", "Reviewer#2026", ["REVIEW_EMPLOYEE"], None, None, None),
    ("عبدالله الشهري", "abdullah.admin@sada.example", "Admin#2026", ["SYSTEM_ADMIN", "REVIEW_EMPLOYEE"], None, None, None),
]


def run() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        roles = {}
        for name in ROLES:
            r = db.execute(select(Role).where(Role.role_name == name)).scalar_one_or_none()
            if r is None:
                r = Role(role_name=name)
                db.add(r)
                db.flush()
            roles[name] = r
        for full_name, email, password, user_roles, acc_no, avail, frozen in USERS:
            u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if u is not None:
                continue
            u = User(full_name=full_name, email=email, password_hash=hash_password(password))
            db.add(u)
            db.flush()
            for rn in user_roles:
                db.add(UserRole(user_id=u.user_id, role_id=roles[rn].role_id))
            if acc_no:
                db.add(BankAccount(
                    customer_id=u.user_id, account_number=acc_no, currency="SAR",
                    available_balance=Decimal(avail), frozen_balance=Decimal(frozen), daily_limit=Decimal("20000.00"),
                ))
        cfg.all_settings(db)
        db.commit()
        print("seed complete")
        for _, email, password, user_roles, *_ in USERS:
            print(f"  {email:40s} {password:16s} {','.join(user_roles)}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
