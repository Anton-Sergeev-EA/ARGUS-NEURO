"""HUST LFP/graphite cells (Mendeley Data nsc7hnsg4s, CC BY 4.0).

77 cells of 1.1 Ah nominal capacity cycled at 30 °C with one charge protocol and
different multi-stage discharge protocols. The archive holds one pickled pandas
structure per cell. Pickle can execute code, so the loader only accepts numpy and
pandas data classes and refuses everything else; the archive checksum is pinned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from argus.battery.calb import to_history
from argus.battery.schema import BatteryRequest

SOURCE = "https://data.mendeley.com/datasets/nsc7hnsg4s/2"
DOWNLOAD = "https://data.mendeley.com/public-files/datasets/nsc7hnsg4s/files/5ca0ac3e-d598-4d07-8dcb-879aa047e98b/file_downloaded"
SHA256 = "071d24617153693b0d29059568525e620f6af6512acc9d00c98c7adcf15125db"
LICENSE = "CC-BY-4.0"
AMBIENT_C = 30.0
ROOT = Path(__file__).resolve().parents[3] / "artifacts/battery-local"
ARCHIVE = ROOT / "hust-raw/our_data.zip"
OUTPUT = ROOT / "hust/cells.json"


class DataOnlyUnpickler(pickle.Unpickler):
    """Allows array and table classes only; any other global is an error."""

    def find_class(self, module: str, name: str) -> Any:
        allowed = (
            module.split(".")[0] == "numpy"
            or module.startswith("pandas.core")
            or module == "pandas._libs.internals"
            or (module == "builtins" and name == "slice")
        )
        if not allowed:
            raise pickle.UnpicklingError(f"blocked {module}.{name}")
        return super().find_class(module, name)


def cell_capacity(raw: bytes) -> tuple[str, np.ndarray]:
    """Discharge capacity in Ah per cycle for one pickled cell."""
    import io

    document = DataOnlyUnpickler(io.BytesIO(raw)).load()
    ((name, cell),) = document.items()
    cycles = sorted(cell["dq"])
    capacity_ah = np.array([float(cell["dq"][c]) for c in cycles]) / 1000.0
    return str(name), capacity_ah


def build_cache(archive: Path = ARCHIVE, output: Path = OUTPUT) -> int:
    with archive.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != SHA256:
            raise ValueError("archive_checksum_mismatch")
    histories: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as bundle:
        for member in sorted(n for n in bundle.namelist() if n.endswith(".pkl")):
            name, capacity = cell_capacity(bundle.read(member))
            history = to_history(
                name, AMBIENT_C, capacity, prefix="HUST", chemistry="lfp"
            )
            histories.append(history.model_dump(mode="json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(histories) + "\n", encoding="utf-8")
    return len(histories)


def load_cache(path: Path = OUTPUT) -> list[BatteryRequest]:
    if not path.exists():
        return []
    return [BatteryRequest.model_validate(i) for i in json.loads(path.read_text())]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(f"{build_cache(args.archive, args.output)} cells written to {args.output}")


if __name__ == "__main__":
    main()
