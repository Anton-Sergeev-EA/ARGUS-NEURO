"""Resolve a validated local model bundle without replacing shipped weights."""

from __future__ import annotations

import json
import os
from pathlib import Path

ARTIFACTS_ROOT = Path(__file__).resolve().parents[2] / "artifacts"


def active_artifacts_dir() -> Path:
    override = os.environ.get("ARGUS_ARTIFACTS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    manifest = ARTIFACTS_ROOT / "active.json"
    if not manifest.exists():
        return ARTIFACTS_ROOT
    payload = json.loads(manifest.read_text())
    relative = Path(payload["directory"])
    resolved = (ARTIFACTS_ROOT / relative).resolve()
    if (
        relative.is_absolute()
        or resolved == ARTIFACTS_ROOT.resolve()
        or not resolved.is_relative_to(ARTIFACTS_ROOT.resolve())
    ):
        raise ValueError("active model directory must be inside artifacts/")
    return resolved
