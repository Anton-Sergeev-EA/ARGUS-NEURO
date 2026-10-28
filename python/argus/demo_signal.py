"""Small, deterministic signal-feature demonstration; no training required."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import numpy as np

from argus.features import extract_features, using_native_core
from argus.features.extraction import FEATURE_NAMES, _extract_features_numpy


def run_demo() -> dict[str, object]:
    """Compare two synthetic waveforms and verify the selected backend."""
    sample_rate = 2048.0
    t = np.arange(2048) / sample_rate
    noise = np.random.default_rng(42).normal(0.0, 0.02, t.size)
    healthy = np.sin(2 * np.pi * 50 * t) + noise
    changed = healthy + 0.8 * np.sin(2 * np.pi * 250 * t)
    cases = {}
    for name, samples in (("healthy", healthy), ("added_250hz", changed)):
        actual = extract_features(samples, sample_rate)
        expected = _extract_features_numpy(samples, sample_rate)
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)
        cases[name] = dict(zip(FEATURE_NAMES, actual.tolist(), strict=True))
    return {
        "source": "synthetic",
        "seed": 42,
        "sample_rate_hz": sample_rate,
        "samples_per_window": t.size,
        "backend": "native_cpp" if using_native_core() else "numpy",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "backend_matches_numpy": True,
        "cases": cases,
        "scope": "Feature illustration only; no fault classifier or field validation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_demo()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Keep previous runs available rather than silently replacing their evidence.
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
