"""UC-01: internal transfer. Covers the 422 business errors, the OTP gate, the atomic
execution path (200) and the risk hold path (202) with its REVIEW_CASE."""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import BankAccount, LedgerEntry, LedgerTransaction, ReviewCase, Transfer


def _accounts(client, headers):
    return client.get("/api/v1/accounts", headers=headers).json()


def _precheck(client, headers, amount, dest="100058329017"):
    acc = _accounts(client, headers)[0]
    return client.post("/api/v1/transfers/precheck", headers=headers, json={
        "source_account_id": acc["account_id"], "destination_account_number": dest, "amount": str(amount),
    })


def _execute(client, headers, amount, otp_id, code, dest="100058329017"):
    acc = _accounts(client, headers)[0]
    return client.post("/api/v1/transfers", headers=headers, json={
        "source_account_id": acc["account_id"], "destination_account_number": dest, "amount": str(amount),
        "otp_id": otp_id, "otp_code": code,
    })


def test_requires_auth(client):
    assert client.get("/api/v1/accounts").status_code == 401


def test_precheck_errors(client, customer):
    assert _precheck(client, customer, 999999).json()["code"] == "INSUFFICIENT_BALANCE"
    assert _precheck(client, customer, 100, dest="000000000000").status_code == 404
    assert _precheck(client, customer, 100, dest="100029485612").json()["code"] == "SAME_ACCOUNT"


def test_invalid_otp_rejected(client, customer):
    pre = _precheck(client, customer, 100).json()
    r = _execute(client, customer, 100, pre["otp_id"], "000000")
    assert r.status_code == 401 and r.json()["code"] == "INVALID_OTP"


def test_small_transfer_completes_atomically(client, customer):
    pre = _precheck(client, customer, 250).json()
    r = _execute(client, customer, 250, pre["otp_id"], pre["dev_otp_code"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED" and body["reference"].startswith("TRF-")

    with SessionLocal() as db:
        src = db.execute(select(BankAccount).where(BankAccount.account_number == "100029485612")).scalar_one()
        dst = db.execute(select(BankAccount).where(BankAccount.account_number == "100058329017")).scalar_one()
        assert src.available_balance == Decimal("24600.00")
        assert dst.available_balance == Decimal("1250.00")
        tx = db.execute(select(LedgerTransaction)).scalar_one()
        entries = db.execute(select(LedgerEntry).where(LedgerEntry.ledger_tx_id == tx.ledger_tx_id)).scalars().all()
        debit = sum(e.amount for e in entries if e.entry_type == "DEBIT")
        credit = sum(e.amount for e in entries if e.entry_type == "CREDIT")
        assert debit == credit == Decimal("250.00")  # double entry holds


def test_otp_cannot_be_reused(client, customer):
    pre = _precheck(client, customer, 10).json()
    assert _execute(client, customer, 10, pre["otp_id"], pre["dev_otp_code"]).status_code == 200
    assert _execute(client, customer, 10, pre["otp_id"], pre["dev_otp_code"]).status_code == 401


def test_large_transfer_is_held_with_case(client, customer):
    pre = _precheck(client, customer, 5000).json()
    r = _execute(client, customer, 5000, pre["otp_id"], pre["dev_otp_code"])
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "HELD"
    assert "LARGE_AMOUNT" in body["triggered_rules"]
    assert body["case_reference"].startswith("REV-")

    with SessionLocal() as db:
        src = db.execute(select(BankAccount).where(BankAccount.account_number == "100029485612")).scalar_one()
        assert src.available_balance == Decimal("19850.00")
        assert src.frozen_balance == Decimal("5000.00")
        assert db.execute(select(LedgerTransaction)).scalar_one_or_none() is None  # money has not moved yet
        case = db.execute(select(ReviewCase)).scalar_one()
        assert case.status == "OPEN" and case.transfer_id is not None and case.ticket_id is None


def test_daily_limit(client, customer):
    for _ in range(4):  # 4 x 4000 = 16000 ok
        pre = _precheck(client, customer, 4000).json()
        assert _execute(client, customer, 4000, pre["otp_id"], pre["dev_otp_code"]).status_code in (200, 202)
    r = _precheck(client, customer, 4500)
    assert r.json()["code"] == "DAILY_LIMIT_EXCEEDED"
