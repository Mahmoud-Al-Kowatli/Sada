# Roadmap and backlog

Priority: P0 = needed for the minimum deliverable agreed in the proposal · P1 = demo quality · P2 = nice to have.
Each item has acceptance criteria; a PR that closes an item must add/extend tests and update docs.

## P0 — minimum deliverable
- [ ] **Browser recording in the sensitive-request screen** (UI 09 "تأكيد صوتي مباشر"): MediaRecorder → WAV (16-bit PCM, 16 kHz) client-side encode → same `POST /tickets`. AC: 10–60 s recording, waveform meter, retry, mic-denied fallback to upload.
- [ ] **Admin screens** (UI 15/16/17): settings form (thresholds, daily limit) with audited save; users & roles table; audit log with filters; ledger view with reverse action (admin only, confirmation). AC: all backed by existing `/admin/*` endpoints; role gating in nav.
- [ ] **B0 trained checkpoint + evaluation report** (see AI_SERVICE.md). AC: service runs with `lfcc_resnet18`, `/health` shows the version, evaluation JSON committed under `ai-service/reports/`.
- [ ] **Model evaluation screen** (UI 16): reads `ai-service/reports/*.json` via a new `GET /admin/model-reports` proxy. AC: EER/AUC per model and per channel condition, confusion matrix, CSV/JSON export.
- [ ] **Alembic autogenerate from 0001** on Postgres; CI job runs both test suites + `npm run build`.

## P1 — demo quality
- [ ] **Live WebRTC call** between customer and support agent (LiveKit or mediasoup), server-side copy of the customer track → 4 s windows → live score on the agent screen. AC: agent sees a 3-colour indicator updating during the call; call unaffected if AI is down.
- [ ] **Redis task queue** for assessments (worker + retry), so `POST /tickets` returns immediately with `assessment_status=PENDING` and the UI polls. AC: killing a worker mid-job does not duplicate records.
- [ ] **Signed webhooks** (`HMAC-SHA256`, `event_id`, retry ×3) for `case.opened`, `case.decided`, `transfer.held`. Institution simulator page to receive them.
- [ ] **Grad-CAM heatmap** in the case screen (AI_SERVICE.md).
- [ ] **Mobile layouts** (UI 18–20): responsive tweaks for home/transfer/support.
- [ ] **Profile page** (UI 22): change password (re-auth), contact data change routed as a sensitive request.
- [ ] **Customer notifications**: ticket/transfer status changes visible in the UI (in-app list; email optional).

## P2 — later
- [ ] Arabic/English UI toggle (copy already structured for it).
- [ ] Multi-account / multi-currency per customer (needs ERD decision on `customer_id` UQ).
- [ ] Loans / deposits / savings goals module.
- [ ] SIP / VoIP provider integration (Asterisk AudioSocket) — documented as future work in the proposal.
- [ ] Speaker-verification cross-check (out of proposal scope; mention only).

## Known gaps / debts
- `references.next_reference` uses a row count; fine for the prototype, replace with a sequence on Postgres.
- `preprocess.to_mono_16k` uses linear interpolation; use `librosa.resample` (kaiser_best) once librosa is installed.
- OTP is simulated (code echoed in dev). Production path would be an SMS provider; keep the hash/expiry design.
- Evidence encryption key is derived from `SADA_JWT_SECRET`; move to a dedicated `SADA_EVIDENCE_KEY`.
- Frontend has no component tests; add Playwright smoke test for the demo script (login → transfer → hold → review).
- Diagram inconsistency to resolve with the team: UC-01 sequence shows the API writing the hold directly while UC-04 routes money through the Ledger Service; the code already routes both through `services/ledger.py` — update the UC-01 diagram.
