"""Client for the Sada AI service. The platform treats the AI as optional: any failure
(timeout, connection refused, 5xx) becomes an UNAVAILABLE assessment and the request
continues with the non-AI risk rules."""
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import get_settings


@dataclass
class AiAssessment:
    status: str  # COMPLETED | INSUFFICIENT_QUALITY | INVALID_AUDIO | UNAVAILABLE
    spoof_score: Decimal | None
    threshold: Decimal | None
    quality_status: str
    model_version: str
    processing_time_ms: int
    external_id: str | None = None
    detail: str | None = None


def assess_audio(file_bytes: bytes, filename: str, reference: str) -> AiAssessment:
    s = get_settings()
    try:
        with httpx.Client(timeout=s.ai_timeout_seconds) as client:
            r = client.post(
                f"{s.ai_service_url}/v1/assessments",
                files={"file": (filename, file_bytes)},
                data={"reference": reference},
            )
        if r.status_code >= 500:
            return AiAssessment("UNAVAILABLE", None, None, "UNKNOWN", "n/a", 0, detail=f"ai http {r.status_code}")
        payload = r.json()
        return AiAssessment(
            status=payload.get("status", "UNAVAILABLE"),
            spoof_score=Decimal(str(payload["spoof_score"])) if payload.get("spoof_score") is not None else None,
            threshold=Decimal(str(payload["threshold"])) if payload.get("threshold") is not None else None,
            quality_status=payload.get("quality_status", "UNKNOWN"),
            model_version=payload.get("model_version", "n/a"),
            processing_time_ms=int(payload.get("processing_time_ms", 0)),
            external_id=payload.get("assessment_id"),
            detail=payload.get("detail"),
        )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        return AiAssessment("UNAVAILABLE", None, None, "UNKNOWN", "n/a", 0, detail=str(e)[:200])
