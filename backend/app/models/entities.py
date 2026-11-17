import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ---------------------------------------------------------------- identity ---
class User(Base):
    __tablename__ = "user"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE | SUSPENDED
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    roles: Mapped[list["Role"]] = relationship(secondary="user_role", lazy="selectin")
    accounts: Mapped[list["BankAccount"]] = relationship(back_populates="customer", lazy="selectin")

    def role_names(self) -> list[str]:
        return [r.role_name for r in self.roles]


class Role(Base):
    __tablename__ = "role"

    role_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(40), unique=True)


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.user_id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.role_id"), primary_key=True)
    assigned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OtpChallenge(Base):
    __tablename__ = "otp_challenge"

    otp_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.user_id"), index=True)
    challenge_hash: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(40), default="TRANSFER")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING | USED | EXPIRED
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------- accounts ---
class BankAccount(Base):
    __tablename__ = "bank_account"

    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    # NOTE: the ERD marks customer_id as UQ (one account per customer). The proposal promises
    # multi-currency accounts, so the uniqueness is intentionally NOT enforced here.
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.user_id"), index=True)
    account_number: Mapped[str] = mapped_column(String(34), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    available_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    frozen_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("20000"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE | FROZEN | CLOSED
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    customer: Mapped["User"] = relationship(back_populates="accounts")

    __table_args__ = (
        CheckConstraint("available_balance >= 0", name="ck_account_available_nonneg"),
        CheckConstraint("frozen_balance >= 0", name="ck_account_frozen_nonneg"),
    )


# ------------------------------------------------------------------ ledger ---
class LedgerTransaction(Base):
    __tablename__ = "ledger_transaction"

    ledger_tx_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfer.transfer_id"), nullable=True)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transaction.ledger_tx_id"), nullable=True, unique=True
    )
    transaction_type: Mapped[str] = mapped_column(String(30))  # TRANSFER | DEPOSIT | WITHDRAWAL | REVERSAL
    status: Mapped[str] = mapped_column(String(20), default="POSTED")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="transaction", lazy="selectin")


class LedgerEntry(Base):
    __tablename__ = "ledger_entry"

    entry_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    ledger_tx_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_transaction.ledger_tx_id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.account_id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(10))  # DEBIT | CREDIT
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    transaction: Mapped["LedgerTransaction"] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_entry_amount_positive"),
        CheckConstraint("entry_type IN ('DEBIT','CREDIT')", name="ck_entry_type"),
    )


class Transfer(Base):
    __tablename__ = "transfer"

    transfer_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(24), unique=True)  # e.g. TRF-2026-10483 (shown in the UI)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.account_id"), index=True)
    destination_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.account_id"), index=True)
    initiated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.user_id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    note: Mapped[str | None] = mapped_column(String(140), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # HELD | COMPLETED | CANCELLED
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfer_amount_positive"),
        CheckConstraint("source_account_id <> destination_account_id", name="ck_transfer_distinct_accounts"),
    )


# ----------------------------------------------------------------- support ---
class SupportTicket(Base):
    __tablename__ = "support_ticket"

    ticket_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(24), unique=True)  # TKT-2026-00852
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.user_id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.account_id"))
    related_transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfer.transfer_id"), nullable=True)
    request_type: Mapped[str] = mapped_column(String(50))  # RAISE_LIMIT | RELEASE_HELD | UPDATE_CONTACT
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))  # SUBMITTED | PENDING_REVIEW | APPROVED | REJECTED
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AudioFile(Base):
    __tablename__ = "audio_file"

    audio_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_ticket.ticket_id"), index=True)
    storage_reference: Mapped[str] = mapped_column(String(500))
    file_format: Mapped[str] = mapped_column(String(10))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    review_copy_status: Mapped[str] = mapped_column(String(20), default="RETAINED")  # RETAINED | DELETED
    retention_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AudioAssessment(Base):
    __tablename__ = "audio_assessment"

    assessment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    audio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audio_file.audio_id"), index=True)
    status: Mapped[str] = mapped_column(String(30))  # COMPLETED | INSUFFICIENT_QUALITY | INVALID_AUDIO | UNAVAILABLE
    spoof_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30))
    model_version: Mapped[str] = mapped_column(String(80), default="n/a")
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    assessed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ------------------------------------------------------------------ review ---
class ReviewCase(Base):
    __tablename__ = "review_case"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(24), unique=True)  # REV-2026-00318
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("support_ticket.ticket_id"), nullable=True)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfer.transfer_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN | IN_REVIEW | ACCEPTED | REJECTED
    triggered_rules: Mapped[str] = mapped_column(Text, default="")  # comma separated rule codes
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.user_id"), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        # exclusive arc: exactly one of ticket_id / transfer_id
        CheckConstraint(
            "(ticket_id IS NOT NULL AND transfer_id IS NULL) OR (ticket_id IS NULL AND transfer_id IS NOT NULL)",
            name="ck_case_exclusive_subject",
        ),
    )


# ------------------------------------------------------------ admin / audit ---
class SystemSetting(Base):
    __tablename__ = "system_setting"

    setting_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    setting_key: Mapped[str] = mapped_column(String(100), unique=True)
    setting_value: Mapped[str] = mapped_column(String(255))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.user_id"), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.user_id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    event_details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    __table_args__ = (UniqueConstraint("audit_id", name="uq_audit_id"),)
