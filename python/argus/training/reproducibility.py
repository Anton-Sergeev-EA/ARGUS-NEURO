"""Small, explicit reproducibility helpers for CPU training."""

from __future__ import annotations

import hashlib
import random
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import torch


def seed_training(seed: int) -> torch.Generator:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    return torch.Generator().manual_seed(seed)


def package_versions() -> dict[str, str]:
    return {
        name: version(name) for name in ("numpy", "torch", "scikit-learn", "pandas")
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_training_config(epochs: int, batch_size: int, lr: float) -> None:
    if epochs < 1 or batch_size < 1 or not np.isfinite(lr) or lr <= 0:
        raise ValueError("epochs, batch_size, and learning rate must be positive")


def classification_metrics(labels: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    tp = int(((predicted == 1) & (labels == 1)).sum())
    fp = int(((predicted == 1) & (labels == 0)).sum())
    fn = int(((predicted == 0) & (labels == 1)).sum())
    tn = int(((predicted == 0) & (labels == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "n_windows_evaluated": int(len(labels)),
    }
