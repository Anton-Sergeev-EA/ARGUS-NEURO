"""Plot a saved demo report. Optional dependency: matplotlib >= 3.6."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new file")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    specs = [
        ("rms", "RMS amplitude", "relative units"),
        (
            "spectral_energy",
            "Spectral energy (DC excluded)",
            "normalized magnitude squared",
        ),
        ("dominant_frequency_hz", "Dominant frequency", "Hz"),
    ]
    for ax, (key, title, unit) in zip(axes, specs, strict=True):
        values = [report["cases"][name][key] for name in ("healthy", "added_250hz")]
        bars = ax.bar(
            ["Baseline", "+250 Hz tone"], values, color=["#247b93", "#c65e33"]
        )
        ax.bar_label(bars, labels=[f"{v:.3f}" for v in values], padding=5)
        ax.set(title=title, ylabel=unit, ylim=(0, max(values) * 1.3))
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "ARGUS-NEURO | A new component can leave the dominant frequency unchanged",
        fontsize=13,
    )
    fig.text(
        0.5,
        0.025,
        "Synthetic illustration · 2,048 samples at 2,048 Hz · seed 42 · no fault classifier or field validation",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.91))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
