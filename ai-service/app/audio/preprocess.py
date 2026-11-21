"""Audio Preprocessor: validation, quality gate, normalisation and windowing (UC-03 steps 3-7).

Only numpy + soundfile are required. Resampling is a simple polyphase-free linear
interpolation which is good enough for 8/44.1/48 kHz -> 16 kHz in the prototype;
swap in librosa.resample when it is installed.
"""
from dataclasses import dataclass

import numpy as np
import soundfile as sf

from app.config import get_settings


class InvalidAudio(Exception):
    pass


@dataclass
class QualityReport:
    duration_seconds: float
    sample_rate: int
    channels: int
    silence_ratio: float
    clipping_ratio: float
    rms_db: float
    status: str  # SUFFICIENT | INSUFFICIENT_QUALITY
    reasons: list[str]


def load_audio(path: str) -> tuple[np.ndarray, int]:
    try:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception as e:  # unreadable / unsupported container
        raise InvalidAudio(f"unreadable audio: {e.__class__.__name__}") from e
    if data.size == 0:
        raise InvalidAudio("empty audio")
    return data, sr


def to_mono_16k(data: np.ndarray, sr: int) -> np.ndarray:
    s = get_settings()
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    if sr != s.target_sample_rate:
        n_out = int(round(len(mono) * s.target_sample_rate / sr))
        x_old = np.linspace(0.0, 1.0, num=len(mono), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
        mono = np.interp(x_new, x_old, mono).astype(np.float32)
    return mono


def normalize(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    return (x / peak * 0.95).astype(np.float32) if peak > 1e-6 else x


def quality_report(data: np.ndarray, sr: int) -> QualityReport:
    s = get_settings()
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    duration = len(mono) / sr
    clipping = float(np.mean(np.abs(mono) >= 0.99)) if mono.size else 1.0
    frame = max(1, int(sr * 0.025))
    n_frames = max(1, len(mono) // frame)
    frames = mono[: n_frames * frame].reshape(n_frames, frame)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    rms_db = 20 * np.log10(rms)
    silence = float(np.mean(rms_db < s.silence_rms_db))
    overall_db = float(20 * np.log10(np.sqrt(np.mean(mono**2) + 1e-12)))

    reasons = []
    if duration < s.min_valid_seconds:
        reasons.append(f"duration {duration:.2f}s < {s.min_valid_seconds}s")
    if duration > s.max_seconds:
        reasons.append(f"duration {duration:.1f}s > {s.max_seconds}s")
    if silence > s.max_silence_ratio:
        reasons.append(f"silence ratio {silence:.2f}")
    if clipping > s.max_clipping_ratio:
        reasons.append(f"clipping ratio {clipping:.3f}")
    status = "SUFFICIENT" if not reasons else "INSUFFICIENT_QUALITY"
    return QualityReport(round(duration, 2), sr, data.shape[1], round(silence, 3), round(clipping, 4), round(overall_db, 1), status, reasons)


def windows(x: np.ndarray) -> list[np.ndarray]:
    """Fixed-length windows with overlap; the last short one is zero-padded (policy: pad, not drop)."""
    s = get_settings()
    win = int(s.window_seconds * s.target_sample_rate)
    hop = int(s.hop_seconds * s.target_sample_rate)
    out: list[np.ndarray] = []
    if len(x) <= win:
        return [np.pad(x, (0, win - len(x)))]
    for start in range(0, len(x) - win + 1, hop):
        out.append(x[start : start + win])
    tail = len(x) - (len(out) - 1) * hop - win if out else len(x)
    if tail > int(s.min_valid_seconds * s.target_sample_rate) * 0.5:
        last = x[(len(out)) * hop :]
        if len(last) >= int(0.5 * win):
            out.append(np.pad(last, (0, win - len(last))))
    return out
