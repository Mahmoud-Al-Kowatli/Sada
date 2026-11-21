"""UC-02 (sensitive request with audio) and UC-04 (review decision) end to end."""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AudioFile, BankAccount, ReviewCase
from tests.conftest import wav_bytes


def _submit(client, customer, request_type="RAISE_LIMIT", filename="voice.wav", data=None):
    acc = client.get("/api/v1/accounts", headers=customer).json()[0]
    return client.post(
        "/api/v1/tickets", headers=customer,
        data={"account_id": acc["account_id"], "request_type": request_type, "description": "أرغب في رفع حد التحويل اليومي إلى 30,000 ر.س"},
        files={"file": (filename, data if data is not None else wav_bytes())},
    )


def test_unsupported_audio_rejected(client, customer, fake_ai):
    fake_ai()
    r = _submit(client, customer, filename="sample.mp3", data=b"ID3\x03\x00garbage")
    assert r.status_code == 400 and r.json()["code"] == "UNSUPPORTED_FORMAT"
    # renaming an mp3 to .wav does not fool the header check
    r = _submit(client, customer, filename="sample.wav", data=b"ID3\x03\x00garbage")
    assert r.status_code == 400


def test_high_score_opens_case(client, customer, fake_ai):
    fake_ai(score=0.87)
    r = _submit(client, customer)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["status"] == "PENDING_REVIEW" and t["case_reference"].startswith("REV-")
    assert Decimal(t["spoof_score"]) == Decimal("0.87")


def test_ai_unavailable_degrades_gracefully(client, customer, fake_ai):
    fake_ai(status="UNAVAILABLE")
    r = _submit(client, customer, request_type="UPDATE_CONTACT")
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["assessment_status"] == "UNAVAILABLE"
    assert t["status"] == "SUBMITTED"  # low-risk request type passes on non-AI rules alone


def test_low_score_sensitive_type_still_reviewed(client, customer, fake_ai):
    fake_ai(score=0.1)
    assert _submit(client, customer, request_type="RAISE_LIMIT").json()["status"] == "SUBMITTED"


def test_review_flow_reject_restores_hold(client, customer, reviewer, fake_ai):
    # create a held transfer first
    acc = client.get("/api/v1/accounts", headers=customer).json()[0]
    pre = client.post("/api/v1/transfers/precheck", headers=customer, json={"source_account_id": acc["account_id"], "destination_account_number": "100058329017", "amount": "6000"}).json()
    r = client.post("/api/v1/transfers", headers=customer, json={"source_account_id": acc["account_id"], "destination_account_number": "100058329017", "amount": "6000", "otp_id": pre["otp_id"], "otp_code": pre["dev_otp_code"]})
    assert r.status_code == 202

    queue = client.get("/api/v1/cases?status=OPEN", headers=reviewer).json()
    assert len(queue) == 1
    case_id = queue[0]["case_id"]

    # decision before claim is refused
    assert client.post(f"/api/v1/cases/{case_id}/decision", headers=reviewer, json={"decision": "REJECTED", "rationale": "لم يتوافق"}).status_code == 409
    assert client.post(f"/api/v1/cases/{case_id}/claim", headers=reviewer).json()["status"] == "IN_REVIEW"
    detail = client.get(f"/api/v1/cases/{case_id}", headers=reviewer).json()
    assert detail["transfer"]["status"] == "HELD" and detail["frozen_balance"] == "6000.00"

    r = client.post(f"/api/v1/cases/{case_id}/decision", headers=reviewer, json={"decision": "REJECTED", "rationale": "المستفيد جديد ولم يتم التحقق هاتفياً"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    with SessionLocal() as db:
        src = db.execute(select(BankAccount).where(BankAccount.account_number == "100029485612")).scalar_one()
        assert src.available_balance == Decimal("24850.00") and src.frozen_balance == Decimal("0.00")


def test_review_flow_accept_settles_transfer(client, customer, reviewer):
    acc = client.get("/api/v1/accounts", headers=customer).json()[0]
    pre = client.post("/api/v1/transfers/precheck", headers=customer, json={"source_account_id": acc["account_id"], "destination_account_number": "100058329017", "amount": "6000"}).json()
    client.post("/api/v1/transfers", headers=customer, json={"source_account_id": acc["account_id"], "destination_account_number": "100058329017", "amount": "6000", "otp_id": pre["otp_id"], "otp_code": pre["dev_otp_code"]})
    case_id = client.get("/api/v1/cases", headers=reviewer).json()[0]["case_id"]
    client.post(f"/api/v1/cases/{case_id}/claim", headers=reviewer)
    r = client.post(f"/api/v1/cases/{case_id}/decision", headers=reviewer, json={"decision": "ACCEPTED", "rationale": "تم التحقق مع العميل هاتفياً"})
    assert r.status_code == 200
    with SessionLocal() as db:
        src = db.execute(select(BankAccount).where(BankAccount.account_number == "100029485612")).scalar_one()
        dst = db.execute(select(BankAccount).where(BankAccount.account_number == "100058329017")).scalar_one()
        assert src.available_balance == Decimal("18850.00") and src.frozen_balance == Decimal("0.00")
        assert dst.available_balance == Decimal("7000.00")


def test_ticket_case_decision_deletes_retained_audio(client, customer, reviewer, fake_ai):
    fake_ai(score=0.9)
    _submit(client, customer)
    case_id = client.get("/api/v1/cases", headers=reviewer).json()[0]["case_id"]
    client.post(f"/api/v1/cases/{case_id}/claim", headers=reviewer)
    assert client.get(f"/api/v1/cases/{case_id}/audio", headers=reviewer).status_code == 200
    client.post(f"/api/v1/cases/{case_id}/decision", headers=reviewer, json={"decision": "REJECTED", "rationale": "الصوت لا يطابق العميل"})
    with SessionLocal() as db:
        audio = db.execute(select(AudioFile)).scalar_one()
        assert audio.review_copy_status == "DELETED" and audio.deleted_at is not None
    assert client.get(f"/api/v1/cases/{case_id}/audio", headers=reviewer).status_code == 404


def test_customer_cannot_access_cases(client, customer):
    assert client.get("/api/v1/cases", headers=customer).status_code == 403
