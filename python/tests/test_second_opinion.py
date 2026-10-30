from __future__ import annotations

from pathlib import Path

import pytest

from argus.battery.schema import BatteryRequest
from argus.battery.second_opinion import META_FILE, MODEL_FILE, second_opinion, train
from test_battery_research import synthetic_history


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("so")
    dataset = root / "cells.json"
    from argus.battery import sampling

    sampling.write_cache(
        dataset,
        {"sampling": sampling.FIXED, "stride": 1, "diagnostic_only": False},
        [synthetic_history(i) for i in range(14)],
    )
    train(dataset, root / "model")
    return root / "model"


def request(**profile: object) -> BatteryRequest:
    data = synthetic_history(3, length=40)
    data["profile"].update(profile)
    return BatteryRequest.model_validate(data)


def test_without_an_installed_model_nothing_is_guessed(tmp_path: Path) -> None:
    assert second_opinion(request(), tmp_path)["status"] == "not_installed"


def test_in_domain_request_gets_a_labelled_estimate(trained: Path) -> None:
    result = second_opinion(request(), trained)
    assert result["status"] == "ok"
    assert result["equivalent_cycles"] >= 0
    assert result["trained_for"]["chemistry"] == "nmc"


@pytest.mark.parametrize(
    "change",
    [
        {"chemistry": "lfp"},
        {"measurement_scope": "pack"},
        {"service_threshold_pct": 70.0},
        {"cycle_axis": "discharge_test_index"},
    ],
)
def test_requests_outside_the_training_domain_are_refused(
    trained: Path, change: dict
) -> None:
    assert second_opinion(request(**change), trained)["status"] == "out_of_domain"


def test_short_history_and_unusual_spacing_are_out_of_domain(trained: Path) -> None:
    short = request()
    short.records = short.records[:5]
    assert second_opinion(short, trained)["status"] == "out_of_domain"
    sparse = request()
    for i, row in enumerate(sparse.records):
        row.equivalent_cycles = float(i * 50)  # 50-cycle spacing, trained on 1
    assert second_opinion(sparse, trained)["status"] == "out_of_domain"


def test_tampered_model_file_is_rejected(trained: Path, tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    copy.mkdir()
    for name in (META_FILE, MODEL_FILE):
        (copy / name).write_bytes((trained / name).read_bytes())
    (copy / MODEL_FILE).write_bytes((copy / MODEL_FILE).read_bytes() + b"x")
    assert second_opinion(request(), copy)["status"] == "model_integrity_error"
