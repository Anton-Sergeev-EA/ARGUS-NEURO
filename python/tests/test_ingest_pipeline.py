"""OCPP mapping, raw store and 5-second resampling (no network, no ocpp package)."""

from __future__ import annotations

import pytest

from argus.ingest.ocpp_mapping import MappedSample, map_meter_value, parse_time
from argus.ingest.resample import engine_rows, resample, summary
from argus.ingest.store import OcppStore

T0 = 1_800_000_000.0
STAMP = "2026-10-30T12:00:00+00:00"


def entry(*items: dict, stamp: str = STAMP) -> dict:
    return {"timestamp": stamp, "sampled_value": list(items)}


def sv(measurand: str, value: object, unit: str | None = None, **extra: object) -> dict:
    out: dict = {"measurand": measurand, "value": str(value), **extra}
    if unit:
        out["unit"] = unit
    return out


def test_maps_every_available_channel_and_never_vibration() -> None:
    sample = map_meter_value(
        entry(
            sv("Voltage", 400, "V"),
            sv("Current.Import", 32, "A"),
            sv("Temperature", 35, "Celsius"),
            sv("Frequency", 50),
            sv("Power.Active.Import", 12.8, "kW"),
            sv("Power.Offered", 22000, "W"),
            sv("Energy.Active.Import.Register", 1234, "Wh"),
        )
    )
    assert sample is not None and sample.issues == ()
    assert sample.channels == {
        "voltage_v": 400.0,
        "current_a": 32.0,
        "temperature_c": 35.0,
        "frequency_hz": 50.0,
        "load_factor": pytest.approx(12800 / 22000),
    }
    assert "vibration_g" not in sample.channels


def test_unit_conversion_and_phase_rules() -> None:
    sample = map_meter_value(
        entry(
            sv("Temperature", 212, "Fahrenheit"),
            sv("Temperature", 300, "K", location="Body"),
            sv("Voltage", 229, "V", phase="L1-N"),
            sv("Voltage", 231, "V", phase="L2-N"),
            sv("Power.Active.Import", 1000, phase="L1"),
            sv("Power.Active.Import", 2000, phase="L2"),
            sv("Power.Offered", 6000),
            sv("Current.Import", 10, phase="L1"),
            sv("Current.Import", 99),  # a total beats the phases
        )
    )
    assert sample is not None
    assert sample.channels["temperature_c"] == pytest.approx(100.0)  # hottest reading
    assert sample.channels["voltage_v"] == 230.0
    assert sample.channels["load_factor"] == pytest.approx(0.5)
    assert sample.channels["current_a"] == 99.0


def test_bad_values_are_reported_not_guessed() -> None:
    sample = map_meter_value(
        entry(
            sv("Voltage", "abc", "V"),
            sv("Current.Import", "nan", "A"),
            sv("Temperature", 20, "Rankine"),
            sv("Frequency", 50, format="SignedData"),
            sv("Power.Offered", 0),
            sv("Power.Active.Import", 100),
        )
    )
    assert sample is not None and sample.channels == {}
    assert set(sample.issues) == {
        "invalid_value:Voltage",
        "invalid_value:Current.Import",
        "unsupported_unit:Temperature",
    }


def test_timestamps_need_a_zone() -> None:
    assert parse_time("2026-10-30T12:00:00") is None
    assert parse_time("nonsense") is None and parse_time(5) is None
    assert parse_time("2026-10-30T12:00:00Z") == parse_time(STAMP)
    assert (
        map_meter_value({"timestamp": "2026-10-30T12:00:00", "sampled_value": []})
        is None
    )


def make_store() -> OcppStore:
    return OcppStore(":memory:")


def test_store_deduplicates_and_logs_problems() -> None:
    store = make_store()
    good = entry(sv("Voltage", 400, "V"), sv("Frequency", 50))
    drift = entry(sv("Voltage", 401, "V"), stamp="2020-01-01T00:00:00+00:00")
    broken = {"timestamp": "no zone", "sampled_value": [sv("Voltage", 1)]}
    now = parse_time(STAMP) or 0.0
    assert store.add_meter_values("ST1", 1, [good], now) == {
        "added": 2,
        "repeated": 0,
        "rejected": 0,
    }
    assert store.add_meter_values("ST1", 1, [good, broken, drift], now) == {
        "added": 1,
        "repeated": 2,
        "rejected": 1,
    }
    assert store.quality("ST1") == {
        "repeated_values": 1,
        "rejected_timestamp": 1,
        "clock_drift": 1,
    }
    assert [s.channels for s in store.samples("ST1", 1)][-1] == {
        "voltage_v": 400.0,
        "frequency_hz": 50.0,
    }


def test_store_never_holds_a_card_identifier() -> None:
    store = make_store()
    columns = {
        row[1]
        for table in ("stations", "meter_values", "ingest_log")
        for row in store._db.execute(f"PRAGMA table_info({table})")
    }
    assert not {c for c in columns if "tag" in c.lower() or "card" in c.lower()}


def full(t: float, **override: float) -> MappedSample:
    channels = {
        "voltage_v": 400.0,
        "current_a": 32.0,
        "temperature_c": 35.0,
        "frequency_hz": 50.0,
        "load_factor": 0.5,
        **override,
    }
    return MappedSample(t, channels)


def test_resample_needs_all_six_channels_and_flags_what_is_missing() -> None:
    rows = resample([full(T0 + 5 * i) for i in range(6)])
    assert len(rows) == 6 and not any(r.complete for r in rows)
    assert all(r.missing == ("vibration_g",) for r in rows)
    vibration = [(T0 + 5 * i, 0.02) for i in range(6)]
    done = resample([full(T0 + 5 * i) for i in range(6)], {"vibration_g": vibration})
    assert all(r.complete for r in done)
    assert len(engine_rows(done)) == 6


def test_resample_does_not_hold_values_past_max_age() -> None:
    samples = [full(T0), full(T0 + 30)]
    vib = {"vibration_g": [(T0, 0.01), (T0 + 30, 0.01)]}
    rows = resample(samples, vib)
    by_time = {r.time_s - T0: r for r in rows}
    assert by_time[0].complete and by_time[30].complete
    assert by_time[5].complete  # held for exactly one step
    assert by_time[10].stale and not by_time[10].complete
    assert set(by_time[10].stale) == set(rows[0].values)
    assert len(engine_rows(rows)) < len(rows)
    info = summary(rows)
    assert info["complete_points"] == 3 and info["grid_points"] == 7


def test_resample_summary_names_channels_that_never_arrived() -> None:
    sample = MappedSample(T0, {"voltage_v": 400.0, "current_a": 1.0})
    info = summary(resample([sample, MappedSample(T0 + 5, sample.channels)]))
    assert "frequency_hz" in info["never_reported"]
    assert resample([]) == []


def test_resample_rejects_a_bad_step_and_huge_spans() -> None:
    with pytest.raises(ValueError):
        resample([full(T0)], step_s=0)
    with pytest.raises(ValueError):
        resample([full(T0), full(T0 + 5 * 300_000)])
