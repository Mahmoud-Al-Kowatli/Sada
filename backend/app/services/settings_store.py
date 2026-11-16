"""Runtime settings kept in SYSTEM_SETTING (thresholds, limits) so staff can change them
from the admin screen without a redeploy. Defaults are seeded on first access."""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting
from app.services.audit import append_audit

DEFAULTS: dict[str, str] = {
    "risk.audio_threshold": "0.65",  # spoof score at/above which a sensitive request is reviewed
    "risk.audio_alert_threshold": "0.85",  # immediate alert + automatic hold
    "risk.large_amount_review": "5000",  # transfer amount at/above which manual review is required
    "risk.new_destination_review_amount": "1000",  # amount at/above which a first-time destination is reviewed
    "risk.repeated_attempts_window_min": "10",
    "risk.repeated_attempts_count": "3",
    "account.default_daily_limit": "20000",
    "audio.retention_days": "30",
}


def get_setting(db: Session, key: str) -> str:
    row = db.execute(select(SystemSetting).where(SystemSetting.setting_key == key)).scalar_one_or_none()
    if row is None:
        if key not in DEFAULTS:
            raise KeyError(key)
        row = SystemSetting(setting_key=key, setting_value=DEFAULTS[key])
        db.add(row)
        db.flush()
    return row.setting_value


def get_decimal(db: Session, key: str) -> Decimal:
    return Decimal(get_setting(db, key))


def get_int(db: Session, key: str) -> int:
    return int(get_setting(db, key))


def set_setting(db: Session, key: str, value: str, actor_id: uuid.UUID) -> SystemSetting:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = db.execute(select(SystemSetting).where(SystemSetting.setting_key == key)).scalar_one_or_none()
    old = row.setting_value if row else DEFAULTS[key]
    if row is None:
        row = SystemSetting(setting_key=key, setting_value=value, updated_by=actor_id)
        db.add(row)
    else:
        row.setting_value = value
        row.updated_by = actor_id
    db.flush()
    append_audit(
        db,
        event_type="UPDATE_SETTING",
        entity_type="SYSTEM_SETTING",
        entity_id=row.setting_id,
        actor_user_id=actor_id,
        details={"key": key, "old": old, "new": value},
    )
    return row


def all_settings(db: Session) -> dict[str, str]:
    return {k: get_setting(db, k) for k in DEFAULTS}
