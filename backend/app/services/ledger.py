"""Ledger Service: the only place that moves money.

Rules enforced here (and nowhere else):
1. Every posted transaction has balanced entries: sum(DEBIT) == sum(CREDIT).
2. Account rows are locked (SELECT ... FOR UPDATE on PostgreSQL) in a fixed order
   before balances are read, so concurrent transfers cannot overdraw an account.
3. Balances are re-checked after the lock; the pre-check done by the API is advisory only.
4. Nothing is updated in place after posting: corrections go through reverse_transaction().

The functions do NOT commit. The caller owns the transaction boundary so that the
transfer row, the case row and the audit row land in the same commit.
"""
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BankAccount, LedgerEntry, LedgerTransaction


class LedgerError(Exception):
    code = "LEDGER_ERROR"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def lock_accounts(db: Session, *account_ids: uuid.UUID) -> dict[uuid.UUID, BankAccount]:
    """Lock the given accounts in a deterministic order (by id) to avoid deadlocks."""
    ordered = sorted(set(account_ids), key=lambda x: str(x))
    rows: dict[uuid.UUID, BankAccount] = {}
    for acc_id in ordered:
        stmt = select(BankAccount).where(BankAccount.account_id == acc_id)
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        acc = db.execute(stmt).scalar_one_or_none()
        if acc is None:
            raise LedgerError(f"account {acc_id} not found", "ACCOUNT_NOT_FOUND")
        rows[acc_id] = acc
    return rows


def _assert_balanced(entries: list[tuple[uuid.UUID, str, Decimal]]) -> None:
    debit = sum((a for _, t, a in entries if t == "DEBIT"), Decimal("0"))
    credit = sum((a for _, t, a in entries if t == "CREDIT"), Decimal("0"))
    if debit != credit or debit <= 0:
        raise LedgerError(f"unbalanced transaction: debit={debit} credit={credit}", "UNBALANCED")


def post_transaction(
    db: Session,
    *,
    transaction_type: str,
    entries: list[tuple[uuid.UUID, str, Decimal]],
    transfer_id: uuid.UUID | None = None,
    reversal_of_id: uuid.UUID | None = None,
    from_frozen: bool = False,
) -> LedgerTransaction:
    """Post a balanced transaction and apply it to account balances.

    entries: (account_id, 'DEBIT'|'CREDIT', amount). DEBIT takes money out of the account,
    CREDIT puts money in. With from_frozen=True the debited amount is taken from
    frozen_balance (releasing a hold) instead of available_balance.
    """
    _assert_balanced(entries)
    accounts = lock_accounts(db, *[a for a, _, _ in entries])

    # apply debits first so an overdraw is detected before any credit is written
    for acc_id, etype, amount in entries:
        acc = accounts[acc_id]
        if etype == "DEBIT":
            if acc.status != "ACTIVE":
                raise LedgerError("source account is not active", "ACCOUNT_INACTIVE")
            if from_frozen:
                if acc.frozen_balance < amount:
                    raise LedgerError("frozen amount missing", "FROZEN_MISMATCH")
                acc.frozen_balance = acc.frozen_balance - amount
            else:
                if acc.available_balance < amount:
                    raise LedgerError("insufficient balance", "INSUFFICIENT_BALANCE")
                acc.available_balance = acc.available_balance - amount
    for acc_id, etype, amount in entries:
        if etype == "CREDIT":
            accounts[acc_id].available_balance = accounts[acc_id].available_balance + amount

    tx = LedgerTransaction(
        transfer_id=transfer_id,
        reversal_of_id=reversal_of_id,
        transaction_type=transaction_type,
        status="POSTED",
        posted_at=_now(),
    )
    db.add(tx)
    db.flush()
    for acc_id, etype, amount in entries:
        db.add(LedgerEntry(ledger_tx_id=tx.ledger_tx_id, account_id=acc_id, entry_type=etype, amount=amount))
    db.flush()
    return tx


def hold_amount(db: Session, account_id: uuid.UUID, amount: Decimal) -> BankAccount:
    """Move amount from available to frozen (no ledger entries: money has not left the account)."""
    acc = lock_accounts(db, account_id)[account_id]
    if acc.status != "ACTIVE":
        raise LedgerError("source account is not active", "ACCOUNT_INACTIVE")
    if acc.available_balance < amount:
        raise LedgerError("insufficient balance", "INSUFFICIENT_BALANCE")
    acc.available_balance = acc.available_balance - amount
    acc.frozen_balance = acc.frozen_balance + amount
    db.flush()
    return acc


def release_hold(db: Session, account_id: uuid.UUID, amount: Decimal) -> BankAccount:
    """Give a held amount back to available (case rejected)."""
    acc = lock_accounts(db, account_id)[account_id]
    if acc.frozen_balance < amount:
        raise LedgerError("frozen amount missing", "FROZEN_MISMATCH")
    acc.frozen_balance = acc.frozen_balance - amount
    acc.available_balance = acc.available_balance + amount
    db.flush()
    return acc


def reverse_transaction(db: Session, original_tx_id: uuid.UUID) -> LedgerTransaction:
    """Create the mirror transaction of a posted one. The original is left untouched."""
    original = db.get(LedgerTransaction, original_tx_id)
    if original is None:
        raise LedgerError("transaction not found", "TX_NOT_FOUND")
    existing = db.execute(
        select(LedgerTransaction).where(LedgerTransaction.reversal_of_id == original_tx_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise LedgerError("transaction already reversed", "ALREADY_REVERSED")
    mirrored = [
        (e.account_id, "CREDIT" if e.entry_type == "DEBIT" else "DEBIT", e.amount) for e in original.entries
    ]
    return post_transaction(db, transaction_type="REVERSAL", entries=mirrored, reversal_of_id=original_tx_id)
