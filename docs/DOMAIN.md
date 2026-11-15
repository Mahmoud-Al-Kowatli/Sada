# Domain model and business rules

## Entities (ERD → `backend/app/models/entities.py`)
| Table | Purpose | Notes |
|---|---|---|
| USER | customers and staff | email UQ, `password_hash` (Argon2id), status ACTIVE/SUSPENDED |
| ROLE / USER_ROLE | RBAC | CUSTOMER, REVIEW_EMPLOYEE, SYSTEM_ADMIN; composite PK on USER_ROLE |
| OTP_CHALLENGE | simulated OTP | `challenge_hash`, `expires_at`, status PENDING/USED/EXPIRED |
| BANK_ACCOUNT | customer account | `available_balance`, `frozen_balance`, `daily_limit`, `account_number` UQ. ERD marks `customer_id` UQ (one account per customer); **not enforced** because the proposal promises multi-currency accounts — decide and align ERD or proposal |
| LEDGER_TRANSACTION | accounting header | `transaction_type` TRANSFER/DEPOSIT/WITHDRAWAL/REVERSAL, `reversal_of_id` self-FK UQ, `transfer_id` nullable |
| LEDGER_ENTRY | accounting lines | DEBIT/CREDIT, amount > 0; a transaction has ≥ 2 balanced entries |
| TRANSFER | customer-facing request | `reference` TRF-…, source/destination FKs, status HELD/COMPLETED/CANCELLED |
| SUPPORT_TICKET | sensitive request | `request_type`, status SUBMITTED/PENDING_REVIEW/APPROVED/REJECTED, optional `related_transfer_id` |
| AUDIO_FILE | metadata of the voice confirmation | `storage_reference` to encrypted file, `review_copy_status` RETAINED/DELETED, `retention_expires_at` |
| AUDIO_ASSESSMENT | result from Sada AI | status COMPLETED/INSUFFICIENT_QUALITY/INVALID_AUDIO/UNAVAILABLE, `spoof_score`, `threshold`, `model_version` |
| REVIEW_CASE | human review | exactly one of `ticket_id`/`transfer_id`; status OPEN/IN_REVIEW/ACCEPTED/REJECTED; `triggered_rules`, reviewer, decision, rationale |
| SYSTEM_SETTING | runtime config | key/value, `updated_by`; defaults in `settings_store.DEFAULTS` |
| AUDIT_LOG | append-only events | polymorphic `entity_type`+`entity_id`, `actor_user_id` nullable (system) |

## Money rules
- Double-entry: `sum(DEBIT) == sum(CREDIT) > 0` per transaction, checked before any balance update.
- Debits are applied before credits so an overdraw fails before anything is written.
- `available_balance ≥ 0` and `frozen_balance ≥ 0` are DB CHECK constraints.
- Daily limit counts today's COMPLETED + HELD transfers from the source account.
- Precheck errors are advisory and fast (422); the authoritative check is under row locks in the ledger.
- Reversal: `reverse_transaction(tx)` posts the mirrored entries as a new REVERSAL transaction; a transaction can be reversed once.

## Risk Engine (`services/risk.py`)
Decision = MANUAL_REVIEW when composite score ≥ 0.5, else PASS. Rules and weights:

Transfers: `LARGE_AMOUNT` (amount ≥ `risk.large_amount_review`, +0.5) · `NEW_DESTINATION` (no prior completed transfer to that account and amount ≥ `risk.new_destination_review_amount`, +0.3) · `REPEATED_ATTEMPTS` (≥ N transfers in M minutes, +0.3).

Sensitive requests: `AUDIO_HIGH_SUSPICION` (score ≥ `risk.audio_alert_threshold`, +1.0) · `AUDIO_SUSPICION` (score ≥ `risk.audio_threshold`, +0.5) · `AUDIO_UNAVAILABLE|INSUFFICIENT_QUALITY|INVALID_AUDIO` (recorded, weight 0) · `SENSITIVE_REQUEST_TYPE` (RAISE_LIMIT/RELEASE_HELD, +0.3) · UPDATE_CONTACT +0.2 · `OPEN_CASE_EXISTS` (+0.2).

Design intent: with ~1 fraud attempt per several hundred calls, the detector must never be the sole decider (base-rate fallacy). It is one input; absence of audio evidence never rejects.

## Settings (SYSTEM_SETTING defaults)
`risk.audio_threshold=0.65` · `risk.audio_alert_threshold=0.85` · `risk.large_amount_review=5000` · `risk.new_destination_review_amount=1000` · `risk.repeated_attempts_window_min=10` · `risk.repeated_attempts_count=3` · `account.default_daily_limit=20000` · `audio.retention_days=30`

## State machines
```
TRANSFER:      (create) ─PASS─▶ COMPLETED
               (create) ─MANUAL_REVIEW─▶ HELD ─accept─▶ COMPLETED
                                          HELD ─reject─▶ CANCELLED
SUPPORT_TICKET: SUBMITTED | PENDING_REVIEW ─accept─▶ APPROVED / ─reject─▶ REJECTED
REVIEW_CASE:    OPEN ─claim─▶ IN_REVIEW ─decision(rationale ≥ 5 chars)─▶ ACCEPTED | REJECTED
AUDIO_FILE:     RETAINED ─case decided or retention expired─▶ DELETED
OTP_CHALLENGE:  PENDING ─verify ok─▶ USED ; ─ttl 300 s─▶ EXPIRED
```

## Audit events in use
REGISTER, LOGIN, CREATE_HOLD, POST_LEDGER, RELEASE_HOLD, CANCEL_HOLD, SUBMIT_SENSITIVE_REQUEST, CLAIM_CASE, CASE_ACCEPTED, CASE_REJECTED, PLAY_AUDIO, UPDATE_SETTING, UPDATE_ROLES, REVERSE_LEDGER.

## Demo data (`scripts/seed.py`)
Ahmad Al-Mansouri (customer, 100029485612, available 24,850 / frozen 5,000 / limit 20,000) · Noura Al-Otaibi (100058329017) · Khaled Al-Salem (100071234455) · Maryam Al-Qahtani (REVIEW_EMPLOYEE) · Abdullah Al-Shehri (SYSTEM_ADMIN + REVIEW_EMPLOYEE). Currency SAR as in the Figma kit (open question: SYP?).
