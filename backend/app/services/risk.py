"""Risk Engine: turns facts about a request into a decision (PASS or MANUAL_REVIEW) plus the
list of rule codes that fired. The Sada AI spoof score is ONE input among others; when the
assessment is unavailable the remaining rules still run (graceful degradation, UC-02)."""
import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transfer
from app.services import settings_store as cfg


@dataclass
class RiskDecision:
    decision: str  # PASS | MANUAL_REVIEW
    triggered_rules: list[str] = field(default_factory=list)
    composite_score: float = 0.0

    @property
    def manual_review(self) -> bool:
        return self.decision == "MANUAL_REVIEW"


def evaluate_transfer(
    db: Session,
    *,
    source_account_id: uuid.UUID,
    destination_account_id: uuid.UUID,
    amount: Decimal,
    initiated_by: uuid.UUID,
) -> RiskDecision:
    rules: list[str] = []
    score = 0.0

    large = cfg.get_decimal(db, "risk.large_amount_review")
    if amount >= large:
        rules.append("LARGE_AMOUNT")
        score += 0.5

    # first time this customer sends money to this destination
    prior = db.scalar(
        select(func.count()).select_from(Transfer).where(
            Transfer.source_account_id == source_account_id,
            Transfer.destination_account_id == destination_account_id,
            Transfer.status == "COMPLETED",
        )
    )
    if not prior and amount >= cfg.get_decimal(db, "risk.new_destination_review_amount"):
        rules.append("NEW_DESTINATION")
        score += 0.3

    # several transfers in a short window
    window = cfg.get_int(db, "risk.repeated_attempts_window_min")
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=window)
    recent = db.scalar(
        select(func.count()).select_from(Transfer).where(
            Transfer.initiated_by == initiated_by, Transfer.created_at >= since
        )
    )
    if (recent or 0) >= cfg.get_int(db, "risk.repeated_attempts_count"):
        rules.append("REPEATED_ATTEMPTS")
        score += 0.3

    decision = "MANUAL_REVIEW" if score >= 0.5 else "PASS"
    return RiskDecision(decision, rules, round(score, 2))


def evaluate_sensitive_request(
    db: Session,
    *,
    request_type: str,
    spoof_score: Decimal | None,
    assessment_status: str,
    open_cases_for_customer: int,
) -> RiskDecision:
    rules: list[str] = []
    score = 0.0

    threshold = cfg.get_decimal(db, "risk.audio_threshold")
    alert = cfg.get_decimal(db, "risk.audio_alert_threshold")
    if assessment_status == "COMPLETED" and spoof_score is not None:
        if spoof_score >= alert:
            rules.append("AUDIO_HIGH_SUSPICION")
            score += 1.0
        elif spoof_score >= threshold:
            rules.append("AUDIO_SUSPICION")
            score += 0.5
    elif assessment_status in ("UNAVAILABLE", "INSUFFICIENT_QUALITY", "INVALID_AUDIO"):
        # no usable audio evidence: the request itself decides, never an automatic rejection
        rules.append(f"AUDIO_{assessment_status}")

    if request_type in ("RAISE_LIMIT", "RELEASE_HELD"):
        rules.append("SENSITIVE_REQUEST_TYPE")
        score += 0.3
    if request_type == "UPDATE_CONTACT":
        score += 0.2

    if open_cases_for_customer > 0:
        rules.append("OPEN_CASE_EXISTS")
        score += 0.2

    decision = "MANUAL_REVIEW" if score >= 0.5 else "PASS"
    return RiskDecision(decision, rules, round(score, 2))
