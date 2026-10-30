"""Post-hoc paired comparison of the two backtest variants, cell by cell.

Reads the rows saved by ``argus.battery.backtest`` and compares the straight line with
the curve chosen by held-out error on the forecast points where both gave a number. The
cell is the unit of resampling. Not preregistered.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

BOOTSTRAPS = 5000
SEED = 7


def _source(cell: str) -> str:
    return cell.split("-")[0] if "-" in cell else "NASA"


def _numeric(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
    return {(c["cell"], c["threshold"], c["observed"]): c for c in rows if "mid" in c}


def paired(detail: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    a, b = _numeric(detail["linear_only"]), _numeric(detail["validated_selection"])
    common = sorted(set(a) & set(b))
    cells = sorted({k[0] for k in common})
    if not cells:
        raise ValueError("no forecast point has a number in both variants")

    def mean_error(table: dict[tuple[Any, ...], dict[str, Any]], cell: str) -> float:
        return float(
            np.mean(
                [
                    abs(table[k]["mid"] - table[k]["truth"])
                    for k in common
                    if k[0] == cell
                ]
            )
        )

    linear = np.array([mean_error(a, c) for c in cells])
    curved = np.array([mean_error(b, c) for c in cells])
    gain = linear - curved
    rng = np.random.default_rng(SEED)
    boot = gain[rng.integers(0, len(cells), (BOOTSTRAPS, len(cells)))].mean(axis=1)
    by_source = {}
    for source in sorted({_source(c) for c in cells}):
        mask = np.array([_source(c) == source for c in cells])
        by_source[source] = {
            "cells": int(mask.sum()),
            "gain_cycles": round(float(gain[mask].mean()), 1),
            "cells_better": int((gain[mask] > 0).sum()),
        }
    return {
        "shared_forecast_points": len(common),
        "cells": len(cells),
        "linear_mae": round(float(linear.mean()), 1),
        "curved_mae": round(float(curved.mean()), 1),
        "gain_cycles": round(float(gain.mean()), 1),
        "gain_ci95": [round(float(x), 1) for x in np.percentile(boot, [2.5, 97.5])],
        "cells_better": int((gain > 0).sum()),
        "by_source": by_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("docs/assets/backtest.json"))
    args = parser.parse_args()
    detail = json.loads(args.input.read_text(encoding="utf-8"))["detail"]
    print(json.dumps(paired(detail), indent=1))


if __name__ == "__main__":
    main()
