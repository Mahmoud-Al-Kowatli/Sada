"""Append-only audit log. Called inside the same DB transaction as the change it describes,
so an audit row never exists without its change and vice versa."""
import json
import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def append_audit(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_user_id=actor_user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        event_details=json.dumps(details or {}, ensure_ascii=False, default=str),
    )
    db.add(row)
    return row
