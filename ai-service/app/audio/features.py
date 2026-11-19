"""LFCC (Linear Frequency Cepstral Coefficients) in plain numpy.

Pipeline: pre-emphasis -> framing (25 ms / 10 ms) -> Hamming -> |FFT|^2 -> linear
triangular filterbank -> log -> DCT-II -> first n_coeffs (+ deltas and delta-deltas).
Matches the LFCC front-end used by the ASVspoof baselines closely enough for the
baseline model; parameters are kept in one place so the training notebook and the
service compute identical features.
"""
import numpy as np

SR = 16000
N_FFT = 512
WIN = int(0.025 * SR)
HOP = int(0.010 * SR)
N_FILTERS = 20
N_COEFFS = 20
PRE_EMPHASIS = 0.97


def _frames(x: np.ndarray) -> np.ndarray:
    x = np.append(x[0], x[1:] - PRE_EMPHASIS * x[:-1])
    n = 1 + max(0, (len(x) - WIN) // HOP)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    return x[idx] * np.hamming(WIN)


def _linear_filterbank() -> np.ndarray:
    edges = np.linspace(0, SR / 2, N_FILTERS + 2)
    bins = np.floor((N_FFT + 1) * edges / SR).astype(int)
    fb = np.zeros((N_FILTERS, N_FFT // 2 + 1))
    for m in range(1, N_FILTERS + 1):
        lo, c, hi = bins[m - 1], bins[m], bins[m + 1]
        for k in range(lo, c):
            fb[m - 1, k] = (k - lo) / max(1, c - lo)
        for k in range(c, hi):
            fb[m - 1, k] = (hi - k) / max(1, hi - c)
    return fb


_FB = _linear_filterbank()


def _dct(n_in: int, n_out: int) -> np.ndarray:
    k = np.arange(n_out)[:, None]
    n = np.arange(n_in)[None, :]
    return np.sqrt(2.0 / n_in) * np.cos(np.pi * k * (2 * n + 1) / (2 * n_in))


_DCT = _dct(N_FILTERS, N_COEFFS)


def _delta(feat: np.ndarray, n: int = 2) -> np.ndarray:
    padded = np.pad(feat, ((n, n), (0, 0)), mode="edge")
    denom = 2 * sum(i * i for i in range(1, n + 1))
    return sum(i * (padded[n + i : len(feat) + n + i] - padded[n - i : len(feat) + n - i]) for i in range(1, n + 1)) / denom


def lfcc(x: np.ndarray, with_deltas: bool = True) -> np.ndarray:
    """Return (T, 60) features: 20 static + 20 delta + 20 delta-delta."""
    power = np.abs(np.fft.rfft(_frames(x), n=N_FFT)) ** 2
    log_energy = np.log(power @ _FB.T + 1e-10)
    static = log_energy @ _DCT.T
    if not with_deltas:
        return static.astype(np.float32)
    d1 = _delta(static)
    d2 = _delta(d1)
    return np.concatenate([static, d1, d2], axis=1).astype(np.float32)
