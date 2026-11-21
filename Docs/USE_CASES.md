# Use cases (as designed in the activity/sequence diagrams and as implemented)

## UC-01 Execute Internal Transfer — `services/transfers.py`, `api/v1/transfers.py`
1. Customer enters destination account + amount (UI validates beneficiary name via `/accounts/lookup`).
2. `POST /transfers/precheck`: session → destination exists / not same / same currency / both ACTIVE → available balance → daily limit. Issues an OTP challenge (dev: code echoed).
3. `POST /transfers`: OTP verified (single use, 5 min) → precheck repeated → Risk Engine.
4. PASS → `ledger.post_transaction` (lock both accounts, recheck, balanced entries, update balances) → Transfer COMPLETED → audit → **200**.
5. MANUAL_REVIEW → `ledger.hold_amount` → Transfer HELD → ReviewCase OPEN → audit → **202**.
Tests: `tests/test_uc01_transfer.py`.

## UC-02 Submit Sensitive Support Request — `services/tickets.py`, `api/v1/tickets.py`
1. Customer picks request type, description, attaches WAV/FLAC (≤ 10 MB). Session validated.
2. Audio validated by header sniffing (extension must match the real format).
3. SupportTicket (SUBMITTED) + AudioFile metadata created; encrypted retained copy written to evidence dir.
4. Sada AI called (8 s timeout). Any failure → assessment UNAVAILABLE.
5. Risk Engine with or without the AI score. MANUAL_REVIEW → ticket PENDING_REVIEW + ReviewCase(ticket). Else SUBMITTED.
6. Audit `SUBMIT_SENSITIVE_REQUEST`, commit → **201** TicketOut.
Tests: `tests/test_uc02_uc04_cases.py` (high score opens case; AI down degrades gracefully; mp3 renamed to .wav rejected).

## UC-03 Analyze Audio Recording — `ai-service/app/main.py`
1. Receive file + reference → write scratch file.
2. `preprocess.load_audio` (soundfile). Unreadable → INVALID_AUDIO (stored, scratch deleted).
3. `quality_report`: duration 3–60 s, silence ratio ≤ 0.85 (frames < −45 dB), clipping ≤ 2 %. Fail → INSUFFICIENT_QUALITY, no score.
4. Mono 16 kHz, peak-normalize, windows of 4 s with 1 s overlap (short tail zero-padded).
5. Classifier scores each window (`StubClassifier` now; `LfccResNet18Classifier` with checkpoint later).
6. Aggregate: mean score + max window and its index (where in the call the suspicion is).
7. Store assessment with threshold, model/preprocess versions, processing time; delete scratch; return.
Tests: `ai-service/tests/test_assess.py`.

## UC-04 Review Suspicious Case — `services/cases.py`, `api/v1/cases.py`
1. Reviewer opens the queue (`GET /cases`), picks a case, **claims** it (OPEN → IN_REVIEW, assigned to them; another reviewer cannot claim it).
2. Evidence bundle: customer, account balances, transfer or ticket, latest audio + assessment, audit timeline.
3. Optional audio playback streamed through the API (audited as PLAY_AUDIO).
4. Decision with mandatory rationale, inside one transaction:
   - ACCEPTED: held transfer settled from frozen balance (ledger entries posted) / ticket APPROVED.
   - REJECTED: hold released to available / ticket REJECTED.
   - Ticket cases: retained audio copy deleted (`review_copy_status=DELETED`, `deleted_at`).
   - Audit `CASE_ACCEPTED|CASE_REJECTED`, commit.
Tests: reject restores hold; accept settles; audio deleted after decision; customer gets 403.

## Demo script for the committee
1. Login as Ahmad → home shows 24,850 available / 5,000 frozen / 20,000 limit.
2. Transfer 1,250 to 100058329017 (Noura) → OTP → COMPLETED (200).
3. Transfer 5,000 → HELD (202), case REV-… created, frozen balance rises, no ledger entries yet.
4. Sensitive request "raise limit" with a WAV → ticket with AI score; stop the AI service and repeat → UNAVAILABLE, request still accepted.
5. Login as Maryam → queue → claim → listen → accept (money moves) or reject (money returns) → audit trail.
