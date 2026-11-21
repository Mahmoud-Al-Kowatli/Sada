"""Simulated OTP (no SMS gateway in the prototype).

The code is generated server-side, stored as an Argon2 hash with an expiry, and in
development the plain code is echoed back in the API response so the demo can proceed.
In production `otp_dev_echo` is false and the code would go through an SMS provider."""
import datetime as dt
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import OtpChallenge


def issue_otp(db: Session, user_id: uuid.UUID, purpose: str = "TRANSFER") -> tuple[OtpChallenge, str | None]:
    s = get_settings()
    code = f"{secrets.randbelow(10**6):06d}"
    challenge = OtpChallenge(
        user_id=user_id,
        purpose=purpose,
        challenge_hash=hash_password(code),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=s.otp_ttl_seconds),
    )
    db.add(challenge)
    db.flush()
    return challenge, (code if s.otp_dev_echo else None)


def verify_otp(db: Session, user_id: uuid.UUID, otp_id: uuid.UUID, code: str) -> bool:
    row = db.execute(
        select(OtpChallenge).where(OtpChallenge.otp_id == otp_id, OtpChallenge.user_id == user_id)
    ).scalar_one_or_none()
    if row is None or row.status != "PENDING":
        return False
    now = dt.datetime.now(dt.timezone.utc)
    exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=dt.timezone.utc)
    if exp < now:
        row.status = "EXPIRED"
        db.flush()
        return False
    if not verify_password(code, row.challenge_hash):
        return False
    row.status = "USED"
    db.flush()
    return True
