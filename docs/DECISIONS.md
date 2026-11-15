# Decision records (short ADRs)

**ADR-1 · The model is a feature, not the core.** Committee feedback: a model-centric project gets zero if the model fails. Sada is a digital bank; deepfake screening is one input of the Risk Engine inside the call-center module. Consequence: every use case must complete with the AI unavailable.

**ADR-2 · Build our own slim banking core instead of Apache Fineract.** Fineract is mature but large, Java, micro-finance oriented; adapting it to a call-center + risk flow in one semester costs more than a focused core (accounts, double-entry ledger, transfers, cases). We borrow its data-model ideas and OBP-API naming.

**ADR-3 · Double-entry ledger with immutable postings.** Balances are cached on BANK_ACCOUNT for speed; LEDGER_ENTRY is the truth. Corrections are reversals, never updates. Lets us prove any balance from entries and audit every movement.

**ADR-4 · Separate frozen balance instead of posting a "pending" entry.** A hold is not an accounting event; the money has not left the account. Posting happens only on acceptance. Rejection just releases the hold. Simpler reconciliation, clearer UI ("available / frozen").

**ADR-5 · Risk Engine returns PASS / MANUAL_REVIEW, never REJECT.** Base-rate argument: fraud is rare per call; any automatic rejection would hit far more legitimate customers than fraudsters. A human decides, with a mandatory rationale, and the audit log records it.

**ADR-6 · AI service is a separate process with its own store.** Independent deployability, separate dependencies (PyTorch), separate failure domain. The platform links results by `assessment_id` and stores a copy of the fields it needs in AUDIO_ASSESSMENT.

**ADR-7 · No score for unusable audio.** Returning a number for silence or clipped audio creates false confidence. The service returns a status; the Risk Engine treats it as "no evidence", not as suspicion.

**ADR-8 · Windows of 4 s, hop 3 s, mean + max aggregation.** Enables a live indicator during a call and localizes suspicion in time (partial spoofing). Mean for stability, max + index for the reviewer.

**ADR-9 · Audio files outside the database, encrypted, time-boxed.** Evidence copies (Fernet) live on disk/object storage; the DB holds metadata and a retention date; the copy is deleted when the case is decided. Playback goes through an authorized, audited endpoint.

**ADR-10 · Feature extraction shared between training and serving.** `ai-service/app/audio/features.py` is imported by the training notebook. Prevents train/serve skew — the most common silent failure in deployed detectors.

**ADR-11 · Stack.** FastAPI + SQLAlchemy 2 + PostgreSQL (SQLite for tests and quick local runs); React + TypeScript + Vite with plain CSS tokens (no UI framework) to match the Figma kit exactly; Argon2id + JWT; Fernet for evidence; docker-compose for one-command setup.

**ADR-12 · OTP simulated.** No SMS provider in the prototype. The challenge is hashed with expiry and single use; the code is echoed in dev only (`SADA_OTP_DEV_ECHO`).

**ADR-13 · Currency SAR in the demo data** because the Figma kit uses it; the proposal is written for Syria. Open decision — one-line change in `scripts/seed.py`.
