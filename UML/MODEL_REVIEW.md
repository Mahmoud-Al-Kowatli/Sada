# Model review — ERD and class diagram, v1 findings and the v2 fix

Reference diagrams: the `.drawio` files in this folder (these are now the
single source of truth for the model, not the code and not any hand-drawn copy).

Reviewed: `ERDE .drawio` and `CLASS DIAGRAM .drawio` in this folder, cross-checked against each other.
Only these two diagrams were changed; the use-case, activity and sequence diagrams are untouched.

| Corrected file | Replaces | Rendered |
|---|---|---|
| [ERD_v2.puml](ERD_v2.puml) | PlantUML block of `ERDE.drawio` | [ERD_v2.png](ERD_v2.png) |
| [CLASS_v2.puml](CLASS_v2.puml) | PlantUML block of `CLASS_DIAGRAM.drawio` | [CLASS_v2.png](CLASS_v2.png) |

Both are wrapped in **one boundary** (`package "Sada Digital Banking Platform"`). The class
diagram's four packages — Enumerations / Domain Model / Application Services / Sada AI
Microservice — are merged into that single boundary, and the process split is carried by the note
on `SadaAIServiceClient` instead.

Both files pass `plantuml -checkonly` with no errors and render correctly.

> **Render them above 4096 px.** PlantUML's default `PLANTUML_LIMIT_SIZE` is 4096 and silently
> **crops** anything wider — v1 of the class diagram is 5821 px wide and was being cut off at the
> right edge. Use `java -DPLANTUML_LIMIT_SIZE=16384 -jar plantuml.jar -tpng CLASS_v2.puml`, or set
> `plantuml.jarArgs` in VS Code. (v2 is 4633 px — merging the packages made it 20 % narrower than
> v1, with a page-friendlier 2.5:1 aspect instead of 4.25:1.)

---

## 1 · Conventions applied

These are the rules the v2 diagram follows. State them once in the report; a reviewer who sees a
consistent convention stops looking for mistakes.

| # | Rule | Why |
|---|---|---|
| R1 | **A foreign key carries the referenced primary key's name verbatim**, optionally prefixed by its role: `[role_]<referenced_pk>`. | `initiated_by` tells you nothing; `initiated_by_user_id` tells you the table, the column and the role. Join conditions become readable and greppable. |
| R2 | The role prefix is used **only** when a table has more than one FK to the same parent, or the role is semantically load-bearing. | `account_id` needs no prefix; `source_account_id` / `destination_account_id` do. |
| R3 | Every `varchar` declares a length; money is `decimal(18,2)`; scores are `decimal(5,4)`. **Never `float` for money.** | Binary floats cannot represent 0.10 exactly. A ledger built on floats fails reconciliation. |
| R4 | Every status/type column has a `CHECK` listing its allowed values. | A free `varchar` status is how `"COMPLETE"`, `"Completed"` and `"COMPLETED"` end up in the same column. |
| R5 | Every FK is indexed unless it is already the leading column of the PK. | Unindexed FKs make every join and every `ON DELETE` check a table scan. |
| R6 | Every user-visible business key (`reference`, `setting_key`, `email`, `account_number`) is `UNIQUE`. | These are what customers quote on the phone. Duplicates are unrecoverable. |
| R7 | **No fact is stored in two tables.** | Two copies drift. The one that drifts is always the one being read. |
| R8 | Every table has `created_at`; event times get their own role names (`posted_at`, `reviewed_at`, `assessed_at`). | "When was the row made" and "when did the thing happen" are different questions. |

---

## 2 · Critical — correctness and security

### C1 · `OTP_CHALLENGE` stores no secret
v1 has `purpose`, `expires_at`, `verified_at`, `status` — **but nothing to verify a code against.**
The class diagram even declares `verify(code : String) : Boolean`, a method the schema makes
impossible to implement.

**Fix:** add `challenge_hash varchar(255) NOT NULL`. Store a hash, never the plain code — an OTP
table is a credential store, and a leaked backup must not hand over live codes.

### C2 · `BANK_ACCOUNT.daily_limit` is missing
The daily transfer limit is a core rule of UC-01. The **class diagram has `dailyLimit`; the ERD does
not.** The two diagrams contradict each other, and as drawn the limit cannot be enforced or varied
per customer.

**Fix:** add `daily_limit decimal(18,2) NOT NULL CHECK (daily_limit > 0)`.

### C3 · `reversal_of_id` is not UNIQUE
v1 marks it `<<FK, nullable>>`. Without `UNIQUE`, one transaction can be reversed any number of
times — **each reversal posts another balanced pair, creating money out of nothing.**

**Fix:** `reversal_of_ledger_tx_id ... <<UQ>>`. This single constraint is what makes "a transaction
is reversible exactly once" true at the database level instead of only in application code.

### C4 · The `REVIEW_CASE` exclusive arc is not modelled
`ticket_id` and `transfer_id` are both nullable FKs with nothing stopping a row from setting **both**
(a case about a ticket *and* a transfer — meaningless) or **neither** (an orphan case).

**Fix:** `CHECK ((ticket_id IS NOT NULL AND transfer_id IS NULL) OR (ticket_id IS NULL AND transfer_id IS NOT NULL))`,
drawn as a note on the entity. Add `UNIQUE` on each so one subject opens at most one case.

### C5 · No CHECK constraints anywhere
As drawn, v1 permits negative balances, zero and negative transfer amounts, an `entry_type` of
`'banana'`, and a transfer from an account to itself.

**Fix:** the constraints listed per column in v2.

---

## 3 · High — integrity and normalisation

| # | Problem | Fix |
|---|---|---|
| H1 | **`AUDIO_FILE.quality_status` duplicates `AUDIO_ASSESSMENT.quality_status`.** Quality is the *outcome of an assessment*, not a property of the file — the same file re-assessed with a new model can yield a different verdict. Two copies of one fact (violates R7). The class diagram agrees: it puts quality only on the assessment. | Remove it from `AUDIO_FILE`. |
| H2 | **No `reference` on `TRANSFER`, `SUPPORT_TICKET`, `REVIEW_CASE`.** The `TRF-2026-10483` / `TKT-…` / `REV-…` numbers shown in the UI and quoted by customers exist nowhere in the model. | Add `reference varchar(24) UNIQUE NOT NULL` to all three. |
| H3 | **`AUDIO_FILE` is missing `review_copy_status`, `retention_expires_at`, `file_size_bytes`** (all three are in the class diagram). The retention policy — keep an encrypted copy, delete it when the case is decided or the window expires — **cannot be expressed**, only `deleted_at` after the fact. | Add all three. |
| H4 | **`REVIEW_CASE` is missing `triggered_rules`** (the class diagram has it). The reviewer sees a `risk_score` but not *which rules fired*, so the decision screen cannot explain itself. | Add `triggered_rules text NOT NULL`. |
| H5 | **`SUPPORT_TICKET` has no `related_transfer_id`.** A "release my held transfer" request cannot point at the transfer it is about. | Add nullable FK to `TRANSFER`. |
| H6 | **`TRANSFER` is missing `completed_at` and `note`** (`completedAt` is in the class diagram). You cannot tell when a transfer actually settled. | Add both. |

---

## 4 · Medium — cardinality errors

| # | v1 | Problem | v2 |
|---|---|---|---|
| M1 | `Ticket \|\|--o{ ReviewCase`<br>`Transfer \|\|--o{ ReviewCase` | Says one ticket (or transfer) may open **many** cases. The rule is **at most one**. | `\|\|--o\|` + `UNIQUE` on both FKs |
| M2 | `Transfer \|\|--o\| LedgerTx` | Says a transfer posts **at most one** transaction. A settled transfer that is later reversed has two rows. | `\|\|--o{` |
| M3 | `Account \|\|--o{ Entry : receives` | Mislabelled — entries both debit **and** credit an account. "Receives" describes only half. | `: affects` |
| M4 | `Audio \|\|--o{ Assessment` | Correct, but nothing marks which assessment is **current** when a file is re-scored. | Documented: latest by `assessed_at`. Add `is_current` only if re-scoring becomes a real flow. |

A note is also added to `LEDGER_ENTRY`: crow's-foot cannot express the `2..*` minimum of
double-entry, so the "at least two, and balanced" rule is stated explicitly.

---

## 5 · Naming — the FK convention (R1/R2)

| v1 column | References | Problem | v2 column |
|---|---|---|---|
| `BANK_ACCOUNT.customer_id` | `USER.user_id` | Drops the referenced PK name — reads like it points at a `CUSTOMER` table that does not exist | `customer_user_id` |
| `TRANSFER.initiated_by` | `USER.user_id` | No `_id` suffix, no target; looks like a boolean or a name | `initiated_by_user_id` |
| `SUPPORT_TICKET.customer_id` | `USER.user_id` | Same as above | `customer_user_id` |
| `REVIEW_CASE.assigned_reviewer_id` | `USER.user_id` | Role is clear but the target is implied, not stated | `assigned_reviewer_user_id` |
| `SYSTEM_SETTING.updated_by` | `USER.user_id` | No `_id`, no target | `updated_by_user_id` |
| `LEDGER_TRANSACTION.reversal_of_id` | `LEDGER_TRANSACTION.ledger_tx_id` | `_of_id` is not a column name; the self-reference is invisible | `reversal_of_ledger_tx_id` |
| `AUDIT_LOG.actor_user_id` | `USER.user_id` | **Already correct** — this is the pattern to copy | unchanged |
| `TRANSFER.source_account_id` / `destination_account_id` | `BANK_ACCOUNT.account_id` | **Already correct** — role + PK name | unchanged |

Other naming fixes:

- `AUDIO_ASSESSMENT.assessment_status` → `status`. Repeating the table name inside a column is noise
  (`assessment.assessment_status`); every other table uses plain `status`.
- `AUDIO_FILE.format` → `file_format`. `format` is a reserved word in several dialects and is
  ambiguous on its own.
- `AUDIO_FILE.uploaded_at` → `created_at`. Same concept as every other table (R8).
- `AUDIO_ASSESSMENT.created_at` → `assessed_at`. It records when the model ran, not when a row
  appeared.
- `AUDIT_LOG.action` → `event_type`, `details` → `event_details`. The table logs *events*; keep one
  vocabulary.
- Added `preprocess_version` to `AUDIO_ASSESSMENT`: a score is not reproducible from `model_version`
  alone — the feature pipeline version is half the answer.

---

## 6 · Low — completeness

- `USER_ROLE` has no `assigned_at`: role grants are a security event and should be dated.
- `LEDGER_TRANSACTION` has only `posted_at`: add `created_at` to distinguish "row written" from
  "money moved".
- `AUDIT_LOG(entity_type, entity_id)` is a deliberate polymorphic soft reference — no FK is possible.
  That is a legitimate pattern, but it must be **stated** (reviewers will flag it as a missing FK)
  and it needs a composite index on `(entity_type, entity_id)`.

---

## 7 · Inconsistencies between the two diagrams

These are worth fixing before submission — a committee that finds the class diagram and the ERD
disagreeing will not trust either.

| Item | Class diagram | ERD v1 |
|---|---|---|
| `BankAccount.dailyLimit` | present | **missing** |
| `AudioFile.sizeBytes`, `reviewCopyStatus`, `retentionExpiresAt` | present | **missing** |
| `AudioFile.qualityStatus` | absent (correct) | **present** (duplicate) |
| `ReviewCase.triggeredRules` | present | **missing** |
| `Transfer.completedAt` | present | **missing** |
| `SystemSetting.updatedBy` | **missing** | present |

Two enum mismatches in the class diagram itself:

- `TransferStatus` declares `PENDING` and `REJECTED`, which the transfer state machine never uses
  (`HELD → COMPLETED | CANCELLED`). Remove them or add them to the state machine — not both.
- `AssessmentStatus` is `COMPLETED | FAILED | UNAVAILABLE`, but the AI service distinguishes
  `INSUFFICIENT_QUALITY` from `INVALID_AUDIO` and never returns `FAILED`. The enum must match what
  the service actually returns, or the "no score for bad audio" rule becomes unreportable.

---

## 8 · One documentation error found while cross-checking

The domain notes in the code repository state: *"the ERD marks `customer_id` UQ (one account per customer)"*. The actual
ERD does **not** mark it unique. Either the note is stale or it refers to an older revision — fix
the note, not the diagram, since multi-currency accounts need the non-unique version anyway.

---

## 9 · Class diagram v2 — what changed

### Structure
The four packages are gone; everything sits in one `package "Sada Digital Banking Platform"`.
The platform/AI process boundary is no longer drawn as a box, so it is stated explicitly in a note
on `SadaAIServiceClient` — the single HTTP dependency is the boundary, and the note records that a
timeout yields `UNAVAILABLE` rather than failing the use case.

### Attributes brought in line with ERD v2
| Class | Change |
|---|---|
| `OtpChallenge` | **added `-challengeHash`** — `verify(code)` was declared on a class with nothing to verify against; also added `createdAt` |
| `Transfer` | added `reference`, `note` |
| `SupportTicket` | added `reference`, `relatedTransferId` |
| `ReviewCase` | added `reference` |
| `SystemSetting` | added `updatedByUserId` (was in the ERD, missing here) |
| `LedgerTransaction` | `reversalOfId` → `reversalOfLedgerTxId`; added `createdAt` |
| `AudioFile` | `format` → `fileFormat`; `sizeBytes` → `fileSizeBytes` |
| `AudioAssessment` | `assessmentStatus` → `status`; `createdAt` → `assessedAt`; added `preprocessVersion` |
| `AuditLog` | `action` → `eventType`; `details` → `eventDetails` |

### Enums corrected and extended
- `TransferStatus`: dropped `PENDING` and `REJECTED` — the state machine is `HELD → COMPLETED | CANCELLED`
  and those two values were unreachable.
- `AssessmentStatus`: dropped `FAILED`, added `INSUFFICIENT_QUALITY` and `INVALID_AUDIO` — the service
  never returns `FAILED`, and collapsing the two bad-audio cases into one would make the
  "no score for unusable audio" rule unreportable.
- Added `UserStatus`, `AccountStatus`, `OtpStatus`, `TransactionType`, `RequestType`,
  `ReviewCopyStatus`, so every attribute that the ERD constrains with a `CHECK` is typed by an enum
  here. The two diagrams now agree value-for-value.
- Attributes retyped from `String` to their enum (`status : UserStatus`, `transactionType : TransactionType`,
  `requestType : RequestType`, `reviewCopyStatus : ReviewCopyStatus`).

### Relationships
- `SupportTicket "0..1" -- "0..*" ReviewCase` → `"1" -- "0..1"`, same for `Transfer`. One subject
  opens **at most one** case, not many.
- `Transfer "1" -- "0..1" LedgerTransaction` → `"1" -- "0..*"`. A settled transfer that is later
  reversed has two ledger transactions.
- `BankAccount -- LedgerEntry : records` → `: affects`. Entries debit *and* credit.
- Added `User "1" -- "0..*" Transfer : initiates` — `initiatedBy` existed in the ERD but the
  association was missing here.
- **`User "1" *-- "0..*" BankAccount` changed from composition to association.** Composition means
  the part cannot outlive the whole: deleting a user would delete their accounts, and with them the
  ledger history. Financial records must survive the customer record. Composition is kept only where
  it is true — `LedgerTransaction *-- LedgerEntry` and `SupportTicket *-- AudioFile`.

### Methods added
`LedgerService.holdAmount()` / `releaseHold()` (UC-01 and UC-04 move money through holds, which v1
had no operation for), `CaseManagementService.claimCase()` (the queue claim step existed in the use
case but not on the class), `OtpChallenge.isExpired()`, and `AuthService.verifyOtp()` now takes the
`otpId` it verifies.
