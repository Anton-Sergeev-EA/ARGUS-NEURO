"""Named parameters of the explainable capacity projection.

Every number that changes a forecast lives here, so a change is visible in review
and can be compared against the regression baselines in ``python/tests/golden``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectionConfig:
    # Observations needed before any trend is reported.
    min_records: int = 8
    # Minimum span of the cycle axis covered by those observations.
    min_span_cycles: float = 10.0
    # Only the most recent comparable observations enter the fit.
    window: int = 30
    # Bootstrap replicates and the fixed seed that makes a report reproducible.
    bootstrap_replicates: int = 400
    seed: int = 41
    # Descriptive interval reported to the user.
    interval_low: float = 0.05
    interval_high: float = 0.95
    # Slope (percentage points per cycle) above which a decline is not trusted.
    decline_slope: float = -0.001
    # Acceleration check needs this many points and a 1.5x steeper recent slope.
    acceleration_min_records: int = 16
    acceleration_ratio: float = 1.5
    # A forecast further than this many observed spans ahead is withheld.
    horizon_spans: float = 5.0
    # Curve family. "linear" is the default because the multi-cell backtest did not show
    # a reliable gain from "auto" (curved model chosen by held-out error).
    model: str = "linear"
    # Curved fits need this many points in the window to be considered.
    nonlinear_min_records: int = 16
    min_fit_points: int = 8
    # Rolling-origin shares of the window used to validate on the newest points.
    validation_origins: tuple[float, ...] = (0.6, 0.75)
    # A curved model must cut the held-out error by this fraction to replace linear.
    required_improvement: float = 0.25
    nonlinear_replicates: int = 200
    # Widen laboratory-cell intervals with the backtest-derived conformal radius.
    calibrate_cells: bool = True
    # Capacity above this share of the reference suggests a wrong reference.
    reference_error_soh_pct: float = 110.0


DEFAULT_CONFIG = ProjectionConfig()
