# Voltage-curve health indicators

Capacity is a late indicator: it has to fall before it can be measured. The shape of the charge curve and the voltage response to current change earlier, so the C++20 core computes them once and Python reuses them through pybind11 (`argus_core`), with a NumPy fallback that follows the same algorithm.

| Indicator | What it is | Why it matters |
|---|---|---|
| ICA peak voltage, height, width | Position, height and full width at half maximum of the dominant dQ/dV peak of a charge | Active-material loss lowers and broadens the peak |
| Voltage rise time | Seconds for the charge voltage to climb between two fixed levels (3.9 → 4.15 V) | A cell with less capacity reaches the upper level sooner at the same current |
| DC internal resistance | `|ΔV| / |ΔI|` across the largest current step | Resistance growth reduces power and raises heat |

Implementation: `cpp_core/include/argus_core/battery_curves.hpp`, tests in `cpp_core/tests/test_battery_curves.cpp` (peak recovery, ageing shift, noisy and repeated voltages, invalid input) and `python/tests/test_battery_curves.py` (native vs NumPy agreement to 1e-9).

## Measured on NASA PCoE cells

Spearman rank correlation between each indicator and capacity-based SOH over every discharge test of a cell. The indicators use raw voltage and current only; no capacity value enters them. Reproduce with `python -m argus.battery.curve_features` (requires the NASA archive described in [PUBLIC_BATTERY_DATA.md](PUBLIC_BATTERY_DATA.md)).

| Cell | tests | ICA peak height | ICA peak width | Rise time | DC resistance |
|---|---|---|---|---|---|
| B0005 | 168 | −0.94 | 0.95 | 0.95 | −0.34 |
| B0006 | 168 | −0.94 | 0.94 | 0.96 | −0.56 |
| B0007 | 168 | −0.92 | 0.93 | 0.95 | −0.38 |
| B0018 | 132 | −0.49 | 0.63 | 0.94 | −0.37 |

Reading the table: the rise time and ICA peak track the capacity fade of all four cells with |ρ| of about 0.9, so they are usable as additional health indicators. DC resistance from the 3-second-spaced NASA samples is weak (the current step falls between two samples), so it is reported but not relied on. These are correlations on four cells of one chemistry and one protocol, not a claim of predictive skill on other cells or on EV packs.
