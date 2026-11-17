# Architecture

## Services
```
Customer Web App / Staff Dashboard (React, :5173)
        │ HTTPS JSON  (/api/v1, Bearer JWT)
        ▼
Sada Platform API (FastAPI, :8000) ──── PostgreSQL (all ERD tables)
   ├─ auth            register/login/me (Argon2id, JWT HS256)
   ├─ accounts        balances, transfer history, beneficiary lookup
   ├─ transfers       UC-01 precheck + OTP, execute (Ledger Service / Risk Engine)
   ├─ tickets         UC-02 sensitive request + audio (Evidence Storage, AI client, Risk Engine)
   ├─ cases           UC-04 queue, claim, evidence, audio stream, decision
   └─ admin           settings, users/roles, audit, ledger, reversal, stats
        │ HTTP multipart (timeout 8 s → UNAVAILABLE)
        ▼
Sada AI (FastAPI, :8100) ──── SQLite assessments.db
   POST /v1/assessments  quality gate → mono 16 kHz → 4 s windows → classifier → aggregate → threshold
```
Redis is provisioned in docker-compose for the planned task queue; not used yet.

## Backend module map (`backend/app`)
| Path | Role |
|---|---|
| `core/config.py` | `Settings` (env prefix `SADA_`), `.env` support |
| `core/db.py` | engine/session, `Base`, `get_db` |
| `core/security.py` | Argon2id hashing, JWT create/decode |
| `models/entities.py` | the 14 ERD tables (see DOMAIN.md) |
| `schemas.py` | Pydantic request/response models |
| `api/deps.py` | `current_user`, `require_roles(...)` |
| `api/v1/*.py` | routers; translate service exceptions to `{code,message}` |
| `services/ledger.py` | **Ledger Service** — the only place balances change |
| `services/transfers.py` | UC-01 orchestration, settle/cancel held transfers |
| `services/risk.py` | **Risk Engine** — `evaluate_transfer`, `evaluate_sensitive_request` |
| `services/tickets.py` | UC-02 orchestration, audio validation, evidence encryption (Fernet) |
| `services/cases.py` | UC-04 claim / evidence bundle / decision (atomic) |
| `services/ai_client.py` | HTTP client to Sada AI with graceful degradation |
| `services/otp.py` | simulated OTP (hash + expiry; dev echo) |
| `services/settings_store.py` | SYSTEM_SETTING defaults + audited updates |
| `services/references.py` | TRF/TKT/REV reference numbers |
| `services/audit.py` | append-only AUDIT_LOG rows |
| `scripts/seed.py` | roles, demo users/accounts matching the Figma mock-ups |
| `alembic/` | migrations (`0001_initial` creates all tables from metadata) |

## Roles
`CUSTOMER` (web app) · `REVIEW_EMPLOYEE` (queue, cases, audio, stats, settings read) · `SYSTEM_ADMIN` (everything + settings write, users/roles, ledger reversal).
A single USER table holds everyone; roles via USER_ROLE.

## API contract (v1)
```
POST /auth/register {full_name,email,password} → 201 {access_token, roles}
POST /auth/login    {email,password}            → 200 {access_token, roles}
GET  /auth/me

GET  /accounts                                   → [AccountOut]   (daily_used computed)
GET  /accounts/{id}/transfers                    → [TransferOut]
GET  /accounts/lookup/{account_number}           → {account_number, display_name, currency}

POST /transfers/precheck {source_account_id,destination_account_number,amount,note?}
                                                 → {ok, destination_name, otp_id, dev_otp_code?}
POST /transfers  {…same + otp_id, otp_code}      → 200 TransferOut(COMPLETED) | 202 TransferOut(HELD, case_reference)
       errors: 401 INVALID_OTP · 404 DESTINATION_NOT_FOUND · 422 INSUFFICIENT_BALANCE | DAILY_LIMIT_EXCEEDED | ACCOUNT_INACTIVE | SAME_ACCOUNT | CURRENCY_MISMATCH

POST /tickets (multipart: account_id, request_type, description, file, related_transfer_id?) → 201 TicketOut
       request_type ∈ RAISE_LIMIT | RELEASE_HELD | UPDATE_CONTACT ; file: WAV/FLAC ≤ 10 MB (header-sniffed)
GET  /tickets · GET /tickets/{id}

GET  /cases?status=OPEN|IN_REVIEW|ACCEPTED|REJECTED   (staff)
POST /cases/{id}/claim · GET /cases/{id} · GET /cases/{id}/audio (audio/wav|flac) · POST /cases/{id}/decision {decision, rationale}

GET/PUT /admin/settings · GET /admin/stats · GET /admin/users · PUT /admin/users/{id}/roles · GET /admin/audit
GET /admin/ledger · POST /admin/ledger/{tx}/reverse

AI: POST /v1/assessments (multipart file, reference) → AssessmentOut ; GET /v1/assessments/{id} ; GET /health
AssessmentOut: {assessment_id, status: COMPLETED|INSUFFICIENT_QUALITY|INVALID_AUDIO, spoof_score?, max_window_score?,
                max_window_index?, threshold?, quality_status, quality{…}, window_scores[], model_version,
                preprocess_version, processing_time_ms, assessed_at}
```

## Frontend map (`frontend/src`)
`api/client.ts` fetch wrapper + types · `auth.tsx` AuthProvider (token in localStorage) · `components/Layout.tsx`
Shell/nav, `Chip`, `AuthHero` · `pages/Auth.tsx` login/register · `pages/Home.tsx` · `pages/Transfers.tsx`
list + 2-step new transfer + result · `pages/Support.tsx` tickets + new sensitive request · `pages/Review.tsx`
queue + case screen · `styles/global.css` tokens.

## Data flow for a held transfer (UC-01 → UC-04)
1. `/transfers` → `transfers.execute_transfer` → `risk.evaluate_transfer` = MANUAL_REVIEW
2. `ledger.hold_amount` (available→frozen), `Transfer(status=HELD)`, `ReviewCase(OPEN, transfer_id)`, audit `CREATE_HOLD`, commit → 202
3. Staff `/cases/{id}/claim` → IN_REVIEW, audit `CLAIM_CASE`
4. `/cases/{id}/decision` ACCEPTED → `transfers.settle_held_transfer` → `ledger.post_transaction(from_frozen=True)` → COMPLETED
   REJECTED → `transfers.cancel_held_transfer` → `ledger.release_hold` → CANCELLED ; audit `CASE_*`; one commit.
