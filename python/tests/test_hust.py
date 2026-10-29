from __future__ import annotations

import hashlib
import os
import pickle
import zipfile
from pathlib import Path

import numpy as np
import pytest

from argus.battery import hust


def cell_pickle(name: str, capacities_mah: list[float]) -> bytes:
    cell = {
        "rul": {},
        "dq": {i + 1: np.float64(c) for i, c in enumerate(capacities_mah)},
        "data": {},
    }
    return pickle.dumps({name: cell})


def test_capacity_is_read_in_ah_in_cycle_order() -> None:
    name, capacity = hust.cell_capacity(cell_pickle("9-9", [1100.0, 1090.0, 1080.0]))
    assert name == "9-9"
    np.testing.assert_allclose(capacity, [1.1, 1.09, 1.08])


class Hostile:
    def __reduce__(self):  # what a malicious pickle would use
        return (os.system, ("echo should-never-run",))


def test_loader_refuses_code_execution_payloads() -> None:
    with pytest.raises(pickle.UnpicklingError, match="blocked"):
        hust.cell_capacity(pickle.dumps({"1-1": Hostile()}))


def test_cache_requires_the_pinned_archive_checksum(tmp_path: Path) -> None:
    archive = tmp_path / "our_data.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("our_data/1-1.pkl", cell_pickle("1-1", [1100.0] * 30))
    assert hashlib.sha256(archive.read_bytes()).hexdigest() != hust.SHA256
    with pytest.raises(ValueError, match="checksum"):
        hust.build_cache(archive, tmp_path / "cells.json")


def test_cache_builds_lfp_cell_histories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "our_data.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for i in range(2):
            bundle.writestr(
                f"our_data/{i}-1.pkl",
                cell_pickle(f"{i}-1", list(1100 - np.arange(60.0))),
            )
    monkeypatch.setattr(
        hust, "SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    assert hust.build_cache(archive, tmp_path / "cells.json") == 2
    cells = hust.load_cache(tmp_path / "cells.json")
    assert {c.profile.battery_id for c in cells} == {"HUST-0-1", "HUST-1-1"}
    assert all(
        c.profile.chemistry == "lfp" and c.profile.measurement_scope == "cell"
        for c in cells
    )
    assert hust.load_cache(tmp_path / "none.json") == []
