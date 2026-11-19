"""Sada AI Controller (UC-03). One endpoint: POST /v1/assessments.

Guarantees:
- the scratch file is deleted on every path (success, invalid, insufficient quality, crash);
- a score is never returned for audio that failed the quality gate;
- every result carries model_version, preprocess_version and the threshold used.
"""
import json
import os
import time
import uuid

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app import store
from app.audio import preprocess as pp
from app.config import get_settings
from app.models.classifiers import build_classifier

settings = get_settings()
app = FastAPI(title=settings.service_name, version="0.1.0")
_classifier = None


def classifier():
    global _classifier
    if _classifier is None:
        _classifier = build_classifier(settings.classifier, settings.checkpoint_path, settings.model_version)
    return _classifier


@app.on_event("startup")
def _startup():
    os.makedirs(settings.scratch_dir, exist_ok=True)
    store.init()


@app.get("/health")
def health():
    return {"status": "ok", "service": "sada-ai", "classifier": settings.classifier, "model_version": classifier().version}


@app.post("/v1/assessments")
async def assess(file: UploadFile = File(...), reference: str = Form(default="")):
    t0 = time.perf_counter()
    scratch = os.path.join(settings.scratch_dir, f"{uuid.uuid4()}.bin")
    try:
        with open(scratch, "wb") as f:
            f.write(await file.read())

        try:
            data, sr = pp.load_audio(scratch)
        except pp.InvalidAudio as e:
            a = store.save(store.Assessment(reference=reference, status="INVALID_AUDIO", quality_status="INVALID",
                                            quality_json=json.dumps({"error": str(e)}), model_version=classifier().version,
                                            processing_time_ms=int((time.perf_counter() - t0) * 1000)))
            return JSONResponse(status_code=200, content={**store.to_dict(a), "detail": str(e)})

        q = pp.quality_report(data, sr)
        if q.status != "SUFFICIENT":
            a = store.save(store.Assessment(reference=reference, status="INSUFFICIENT_QUALITY", quality_status="INSUFFICIENT_QUALITY",
                                            quality_json=json.dumps(q.__dict__), model_version=classifier().version,
                                            processing_time_ms=int((time.perf_counter() - t0) * 1000)))
            return store.to_dict(a)

        x = pp.normalize(pp.to_mono_16k(data, sr))
        wins = pp.windows(x)
        scores = classifier().score_windows(wins)
        mean_score = round(float(sum(scores) / len(scores)), 4)
        max_i = max(range(len(scores)), key=lambda i: scores[i])
        a = store.save(store.Assessment(
            reference=reference, status="COMPLETED", spoof_score=mean_score, max_window_score=scores[max_i], max_window_index=max_i,
            threshold=settings.threshold, quality_status="SUFFICIENT", quality_json=json.dumps(q.__dict__),
            window_scores_json=json.dumps(scores), model_version=classifier().version,
            processing_time_ms=int((time.perf_counter() - t0) * 1000),
        ))
        return store.to_dict(a)
    finally:
        try:
            os.remove(scratch)
        except FileNotFoundError:
            pass


@app.get("/v1/assessments/{assessment_id}")
def get_assessment(assessment_id: uuid.UUID):
    with store.session() as db:
        a = db.get(store.Assessment, assessment_id)
    if a is None:
        return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "message": "assessment not found"})
    return store.to_dict(a)
