import io
import os

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

os.environ["SADA_AI_ASSESSMENTS_DB"] = "sqlite:///./var/test-assessments.db"
from app.main import app  # noqa: E402

client = TestClient(app)


def wav(seconds=5.0, sr=16000, kind="tone"):
    t = np.arange(int(seconds * sr)) / sr
    if kind == "tone":
        x = 0.3 * np.sin(2 * np.pi * 220 * t) + 0.05 * np.random.default_rng(0).standard_normal(len(t))
    elif kind == "silence":
        x = np.zeros(len(t))
    else:  # clipped
        x = np.clip(3 * np.sin(2 * np.pi * 220 * t), -1, 1)
    buf = io.BytesIO()
    sf.write(buf, x.astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_health():
    with client:
        assert client.get("/health").json()["status"] == "ok"


def test_completed_assessment_has_traceability():
    with client:
        r = client.post("/v1/assessments", files={"file": ("a.wav", wav())}, data={"reference": "TKT-1"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "COMPLETED" and 0 <= b["spoof_score"] <= 1
    assert b["threshold"] == 0.65 and b["model_version"] and b["preprocess_version"]
    assert len(b["window_scores"]) >= 1 and b["quality"]["status"] == "SUFFICIENT"
    assert client.get(f"/v1/assessments/{b['assessment_id']}").status_code == 200


def test_resampling_44k():
    with client:
        b = client.post("/v1/assessments", files={"file": ("a.wav", wav(sr=44100))}).json()
    assert b["status"] == "COMPLETED" and b["quality"]["sample_rate"] == 44100


def test_silence_and_short_audio_are_insufficient():
    with client:
        b = client.post("/v1/assessments", files={"file": ("a.wav", wav(kind="silence"))}).json()
        assert b["status"] == "INSUFFICIENT_QUALITY" and b["spoof_score"] is None
        b = client.post("/v1/assessments", files={"file": ("a.wav", wav(seconds=1.0))}).json()
        assert b["status"] == "INSUFFICIENT_QUALITY"
        b = client.post("/v1/assessments", files={"file": ("a.wav", wav(kind="clipped"))}).json()
        assert b["status"] == "INSUFFICIENT_QUALITY"


def test_garbage_is_invalid_and_scratch_is_cleaned():
    with client:
        b = client.post("/v1/assessments", files={"file": ("a.wav", b"not audio at all")}).json()
    assert b["status"] == "INVALID_AUDIO"
    assert not os.listdir("./var/scratch")
