"""Pydantic request/response models (the API contract)."""
import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ------------------------------------------------------------------- auth ---
class RegisterIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(not c.isalnum() for c in v):
            raise ValueError("كلمة المرور يجب أن تحوي رقماً ورمزاً خاصاً")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    roles: list[str]


class UserOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    status: str
    roles: list[str]
    created_at: dt.datetime


# --------------------------------------------------------------- accounts ---
class AccountOut(BaseModel):
    account_id: uuid.UUID
    account_number: str
    currency: str
    available_balance: Decimal
    frozen_balance: Decimal
    daily_limit: Decimal
    daily_used: Decimal = Decimal("0")
    status: str


# -------------------------------------------------------------- transfers ---
class TransferPrecheckIn(BaseModel):
    source_account_id: uuid.UUID
    destination_account_number: str = Field(min_length=6, max_length=34)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    note: str | None = Field(default=None, max_length=140)


class TransferPrecheckOut(BaseModel):
    ok: bool
    destination_name: str
    otp_id: uuid.UUID
    dev_otp_code: str | None = None  # only in development


class TransferExecuteIn(TransferPrecheckIn):
    otp_id: uuid.UUID
    otp_code: str = Field(min_length=6, max_length=6)


class TransferOut(BaseModel):
    transfer_id: uuid.UUID
    reference: str
    amount: Decimal
    status: str
    destination_account_number: str
    destination_name: str | None = None
    note: str | None
    created_at: dt.datetime
    completed_at: dt.datetime | None
    triggered_rules: list[str] = []
    case_reference: str | None = None


# ---------------------------------------------------------------- tickets ---
class TicketOut(BaseModel):
    ticket_id: uuid.UUID
    reference: str
    request_type: str
    description: str
    status: str
    created_at: dt.datetime
    assessment_status: str | None = None
    spoof_score: Decimal | None = None
    case_reference: str | None = None


# ------------------------------------------------------------------ cases ---
class CaseSummaryOut(BaseModel):
    case_id: uuid.UUID
    reference: str
    status: str
    subject_type: str  # TRANSFER | TICKET
    subject_reference: str
    customer_name: str
    triggered_rules: list[str]
    spoof_score: Decimal | None = None
    assessment_status: str | None = None
    assigned_reviewer_id: uuid.UUID | None = None
    created_at: dt.datetime


class CaseDetailOut(CaseSummaryOut):
    customer_email: str
    account_number: str
    available_balance: Decimal
    frozen_balance: Decimal
    transfer: TransferOut | None = None
    ticket: TicketOut | None = None
    assessment: dict | None = None
    audio_available: bool = False
    decision: str | None = None
    decision_rationale: str | None = None
    reviewed_at: dt.datetime | None = None
    timeline: list[dict] = []


class CaseDecisionIn(BaseModel):
    decision: str
    rationale: str = Field(min_length=5, max_length=2000)


# ------------------------------------------------------------------ admin ---
class SettingsOut(BaseModel):
    settings: dict[str, str]


class SettingUpdateIn(BaseModel):
    key: str
    value: str = Field(min_length=1, max_length=255)


class AuditOut(BaseModel):
    audit_id: uuid.UUID
    actor_name: str | None
    event_type: str
    entity_type: str
    entity_id: uuid.UUID
    event_details: str
    created_at: dt.datetime


class ApiError(BaseModel):
    code: str
    message: str
