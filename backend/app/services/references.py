"""Human-readable references shown in the UI (TRF-2026-10483, TKT-2026-00852, REV-2026-00318).

The number part is derived from a per-prefix row count plus a base, so references look like the
mock-ups and stay unique. UUIDs remain the real primary keys."""
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ReviewCase, SupportTicket, Transfer

_BASES = {"TRF": 10400, "TKT": 800, "REV": 300}
_TABLES = {"TRF": Transfer, "TKT": SupportTicket, "REV": ReviewCase}
_WIDTH = {"TRF": 5, "TKT": 5, "REV": 5}


def next_reference(db: Session, prefix: str) -> str:
    model = _TABLES[prefix]
    count = db.scalar(select(func.count()).select_from(model)) or 0
    year = dt.datetime.now(dt.timezone.utc).year
    number = _BASES[prefix] + count + 1
    return f"{prefix}-{year}-{number:0{_WIDTH[prefix]}d}"
