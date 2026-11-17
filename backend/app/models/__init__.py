"""ORM models. One class per ERD entity, same names and columns as the diagram.

Design notes that matter when reading the diagram:
- USER is a single table for customers and staff; what a user may do comes from USER_ROLE.
- BANK_ACCOUNT keeps available_balance and frozen_balance apart: a transfer that is held
  for review moves money from available to frozen without leaving the account.
- LEDGER_TRANSACTION / LEDGER_ENTRY is the accounting truth (double entry). A posted
  transaction is never edited; it is reversed by another transaction (reversal_of_id).
- TRANSFER is the customer-facing request; it only gets a ledger transaction once executed.
- REVIEW_CASE points at either a ticket or a transfer (exclusive arc, enforced by a CHECK).
- AUDIT_LOG is append-only; entity_type + entity_id form a polymorphic reference.
"""
from app.models.entities import (  # noqa: F401
    AudioAssessment,
    AudioFile,
    AuditLog,
    BankAccount,
    LedgerEntry,
    LedgerTransaction,
    OtpChallenge,
    ReviewCase,
    Role,
    SupportTicket,
    SystemSetting,
    Transfer,
    User,
    UserRole,
)
