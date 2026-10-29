# EV battery capacity, life projection and care

The battery page is the default landing page at `/`. Equipment diagnostics remain available at `/equipment.html`. Start the existing server with `bash scripts/run_dashboard.sh` and select **Explore an illustrative example**, or import your own CSV.

The interface offers English (default), Russian, Chinese, Hindi, Spanish, French, German, Japanese and Italian. Both pages share the language preference saved in the browser. No build step or external translation service is used.

**No personal measurements are required to start:** use the published NASA cell selector. Four measured histories are available after one-time local preparation. Source, checksums, scope and installation are documented in [PUBLIC_BATTERY_DATA.md](PUBLIC_BATTERY_DATA.md). These records remain cell-level laboratory measurements, with no EV-pack or calendar-life claim.

## Measurements

Capacity-based SOH is `100 × measured_capacity_ah / reference_capacity_ah`. It is different from SOC (the present charge percentage). Supply full controlled capacity tests at comparable temperature, discharge rate and cutoff conditions. A partial discharge's Ah throughput is not a full capacity measurement.

CSV columns:

```csv
equivalent_cycles,capacity_ah,condition_id,temperature_c
0,100,same-control-test,25
100,96,same-control-test,25
200,92,same-control-test,25
300,88,same-control-test,25
```

This four-row example illustrates the format; a life projection requires at least eight comparable records spanning at least ten cycles. Rows must be strictly increasing by cycle index, unique, finite and positive in capacity. Limits: 2 MB and 2,000 records. The downloaded example includes a `data_origin=synthetic` column; its origin remains visibly marked after upload. An unmarked upload is labelled user-supplied, not automatically verified field data.

Choose a reference capacity in **Ah**, not kWh, and an identifier matching `condition_id`. Measurements under other conditions are excluded. A reference error (capacity above 110% of reference) or excluded conditions suppresses the life projection. SOH can exceed 100%; it is not silently clipped.

## Life projection

The last 30 comparable observations are fitted with a linear capacity trend. Four hundred moving-block residual bootstrap fits (seed 41) provide descriptive 5th–95th percentile estimates of cycles until the configured capacity threshold.

Numbers are withheld for short history, no reliable decline, accelerating degradation, an operating alert, or a projection more than five observed spans into the future.

For laboratory cells (`measurement_scope=cell`) the interval is widened with a conformal radius learned from a 31-cell backtest, because the plain bootstrap interval covered the truth only 22% of the time; the calibrated interval covered 90% on cells it had not seen (leave-one-cell-out). Pack reports keep the plain interval and are labelled that way. Details and limits: [BACKTEST.md](BACKTEST.md), [METHODOLOGY.md](METHODOLOGY.md). Voltage-curve indicators (dQ/dV peak, voltage rise time) computed by the C++ core: [CURVES.md](CURVES.md). When the configured threshold is already reached, remaining cycles to that threshold are zero. The threshold is application-specific; 80% is a default example, not a universal safety or warranty limit.

Calendar months are shown only when the input axis is equivalent full cycles and a monthly cycle rate is supplied. They are a usage scenario, not a separate calendar-aging model. This calculation does not include a calibrated temperature/chemistry aging model, survival censoring, future failures or changes in use. Bootstrap intervals do not establish field coverage; noiseless illustrative data can produce equal endpoints, shown as an approximate value in the UI.

An independent laboratory cell history uses `measurement_scope=cell` and `cycle_axis=discharge_test_index`. It is not an EV-pack result and is never converted to calendar months. Existing experimental TCN/GRU training utilities are separate from this explainable production route. No trained cell model is presented as a validated vehicle-pack predictor.

## Recommendations

Recommendations contain a code, priority, observed evidence, source and a translated action with a verification step:

- Reported BMS alarm: follow the exact warning and diagnostic instructions.
- Charging outside supplied manufacturer temperature limits: follow the approved thermal-management procedure; no universal temperature values are invented.
- Cell voltage spread above the supplied manufacturer limit: repeat under comparable conditions and arrange diagnostics if persistent.
- Reported hot storage at high charge: review the manufacturer's storage guidance.
- Reported frequent DC fast charging: review approved AC charging and preconditioning options where compatible with required trips.
- Capacity threshold reached: assess practical suitability and service needs.
- Missing model-specific limits: obtain them from the correct manufacturer manual.

No quantified lifetime gain or universal charging percentage is promised. Chemistry, operating temperature, charging patterns and thermal systems affect battery life: [U.S. DOE AFDC](https://afdc.energy.gov/fuels/electricity-benefits). Model-specific advice should come from the vehicle manufacturer: [Australian Government energy guidance](https://www.energy.gov.au/electric-vehicles/electric-vehicle-basics/electric-vehicle-batteries-and-motors).

Capacity-based SOH does not establish electrical, thermal or crash safety. There is no OBD/CAN connection, hardware write or charger control in this implementation. No driving range is inferred from Ah.

## API and local reports

| Route | Behavior |
|---|---|
| `GET /api/battery/datasets` | Fixed public-data catalogue and cache availability |
| `GET /api/battery/datasets/{dataset_id}?observations=40` | Selected observed prefix and provenance |
| `GET /api/battery/example` | Opt-in synthetic EV history |
| `POST /api/battery/import-csv` | Validate CSV and preserve explicit synthetic provenance |
| `POST /api/battery/analyze` | Capacity, trend, conditional life and care recommendations; no persistence |
| `POST /api/battery/save` | Explicit local SQLite report storage |
| `GET /api/battery/history/{battery_id}` | Up to 50 saved reports for this battery, newest first |
| `GET /api/battery/history/{battery_id}/changes` | Direction of capacity and remaining life between the two newest saved reports (no safety verdict) |

`analyze`, `save` and `import-csv` are limited to 60 requests per minute per client (`ARGUS_BATTERY_RATE_LIMIT`); excess requests receive `429` with `Retry-After`. Reports carry `schema_version` 2. Saving an identical report twice in a row stores it once; different reports build a timeline. The request schema is available in `/docs`. Manufacturer limits require a source. Reports include a content-derived assessment ID, source, comparable history and limitations. Export downloads the report JSON. Local history is stored in `artifacts/battery-local/history.sqlite3` and excluded from version control. No data is sent to external services by these routes. Use the application locally; it does not implement multi-user access controls.

## Verification

```bash
python -m pip install -r python/requirements-dev.txt
bash scripts/build_cpp_core.sh
ctest --test-dir build --output-on-failure
PYTHONPATH="$PWD/python:$PWD/build/cpp_core" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest python/tests -q
ruff check python
ruff format --check python
node --test web/dashboard/tests/*.test.cjs
```

Tests cover known degradation trajectories, refusal states, SOC/SOH separation, manufacturer limits, malformed CSV, synthetic provenance, local persistence, HTTP limits and complete translation dictionaries.
