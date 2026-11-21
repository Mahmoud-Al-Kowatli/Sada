"""Deepfake Classifier component. One interface, two implementations:

- StubClassifier: deterministic, weight-free. Produces a stable score from simple signal
  statistics so the whole platform can be exercised before training finishes. It is NOT a
  detector and says so in model_version.
- LfccResNet18Classifier: the B0 baseline from the proposal (LFCC -> ResNet-18 -> 2 classes),
  loaded from a PyTorch checkpoint produced by the training notebook. Imported lazily so the
  service runs without torch installed.
"""
from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from app.audio.features import lfcc


class Classifier(Protocol):
    version: str

    def score_windows(self, windows: list[np.ndarray]) -> list[float]: ...


class StubClassifier:
    version = "stub-0.1 (not a detector)"

    def score_windows(self, windows: list[np.ndarray]) -> list[float]:
        out = []
        for w in windows:
            feats = lfcc(w, with_deltas=False)
            # a content-derived pseudo-score in [0.05, 0.95]: stable per input, meaningless as evidence
            h = hashlib.sha256(np.round(feats.mean(axis=0), 2).tobytes()).digest()
            out.append(round(0.05 + 0.9 * (int.from_bytes(h[:4], "big") / 2**32), 4))
        return out


class LfccResNet18Classifier:
    def __init__(self, checkpoint_path: str, version: str):
        import torch

        from app.models.lfcc_resnet18 import LfccResNet18

        self.torch = torch
        self.net = LfccResNet18(n_classes=2)
        state = torch.load(checkpoint_path, map_location="cpu")
        self.net.load_state_dict(state.get("state_dict", state))
        self.net.eval()
        self.version = version

    def score_windows(self, windows: list[np.ndarray]) -> list[float]:
        torch = self.torch
        feats = np.stack([lfcc(w) for w in windows])  # (N, T, 60)
        x = torch.from_numpy(feats).unsqueeze(1).transpose(2, 3)  # (N, 1, 60, T)
        with torch.no_grad():
            logits = self.net(x)
            prob_spoof = torch.softmax(logits, dim=1)[:, 1]
        return [round(float(p), 4) for p in prob_spoof]


def build_classifier(name: str, checkpoint_path: str, version: str) -> Classifier:
    if name == "lfcc_resnet18":
        return LfccResNet18Classifier(checkpoint_path, version)
    return StubClassifier()
