"""Tests run against an in-memory SQLite database and a fake Sada AI client."""
import os
from decimal import Decimal

os.environ["SADA_DATABASE_URL"] = "sqlite://"
os.environ["SADA_ENVIRONMENT"] = "test"
os.environ["SADA_EVIDENCE_DIR"] = "./var/test-evidence"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.pool import StaticPool

from app.core import db as dbmod
from app.core.db import Base
from app.core.security import hash_password
from app.main import app
from app.models import BankAccount, Role, User, UserRole

# single shared in-memory connection for the whole test session
dbmod.engine = dbmod.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
dbmod.SessionLocal.configure(bind=dbmod.engine)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(dbmod.engine)
    Base.metadata.create_all(dbmod.engine)
    db = dbmod.SessionLocal()
    roles = {}
    for name in ("CUSTOMER", "REVIEW_EMPLOYEE", "SYSTEM_ADMIN"):
        roles[name] = Role(role_name=name)
        db.add(roles[name])
    db.flush()

    def mk(name, email, pw, role, acc_no=None, avail="0", frozen="0"):
        u = User(full_name=name, email=email, password_hash=hash_password(pw))
        db.add(u)
        db.flush()
        db.add(UserRole(user_id=u.user_id, role_id=roles[role].role_id))
        if acc_no:
            db.add(BankAccount(customer_id=u.user_id, account_number=acc_no, available_balance=Decimal(avail), frozen_balance=Decimal(frozen), daily_limit=Decimal("20000")))
        return u

    mk("أحمد", "ahmad@example.com", "Customer#2026", "CUSTOMER", "100029485612", "24850.00", "0")
    mk("نورة", "noura@example.com", "Customer#2026", "CUSTOMER", "100058329017", "1000.00", "0")
    mk("مريم", "maryam@sada.example", "Reviewer#2026", "REVIEW_EMPLOYEE")
    mk("عبدالله", "admin@sada.example", "Admin#2026", "SYSTEM_ADMIN")
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def customer(client):
    return login(client, "ahmad@example.com", "Customer#2026")


@pytest.fixture
def reviewer(client):
    return login(client, "maryam@sada.example", "Reviewer#2026")


@pytest.fixture
def admin(client):
    return login(client, "admin@sada.example", "Admin#2026")


@pytest.fixture
def fake_ai(monkeypatch):
    """Control the AI result from a test: fake_ai(score=0.9) or fake_ai(status='UNAVAILABLE')."""
    from app.services import ai_client, tickets

    def _set(status="COMPLETED", score=0.2, quality="SUFFICIENT"):
        def _assess(file_bytes, filename, reference):
            return ai_client.AiAssessment(status, Decimal(str(score)) if status == "COMPLETED" else None, Decimal("0.65"), quality, "stub-test", 5)
        monkeypatch.setattr(tickets.ai_client, "assess_audio", _assess)

    return _set


def wav_bytes(seconds: float = 4.0, rate: int = 16000) -> bytes:
    """A valid 16-bit mono WAV of silence (header is what the backend validates)."""
    import struct

    n = int(seconds * rate)
    data = b"\x00\x00" * n
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(data))
    return header + data
