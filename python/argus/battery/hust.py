"""HUST LFP/graphite cells (Mendeley Data nsc7hnsg4s, CC BY 4.0).

77 cells of 1.1 Ah nominal capacity cycled at 30 °C with one charge protocol and
different multi-stage discharge protocols. The archive holds one pickled pandas
structure per cell. Pickle can execute code, so the loader only accepts numpy and
pandas data classes and refuses everything else; the archive checksum is pinned.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import pickle
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from argus.battery import sampling
from argus.battery.calb import to_history
from argus.battery.schema import BatteryRequest

SOURCE = "https://data.mendeley.com/datasets/nsc7hnsg4s/2"
DOWNLOAD = "https://data.mendeley.com/public-files/datasets/nsc7hnsg4s/files/5ca0ac3e-d598-4d07-8dcb-879aa047e98b/file_downloaded"
SHA256 = "071d24617153693b0d29059568525e620f6af6512acc9d00c98c7adcf15125db"
LICENSE = "CC-BY-4.0"
AMBIENT_C = 30.0
ROOT = Path(__file__).resolve().parents[3] / "artifacts/battery-local"
ARCHIVE = ROOT / "hust-raw/our_data.zip"
# Legacy cache written with the length-dependent stride; diagnostic use only.
LEGACY_OUTPUT = ROOT / "hust/cells.json"
OUTPUT = ROOT / f"hust/cells-fixed-stride{sampling.DEFAULT_STRIDE}.json"


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


def cell_series(raw: bytes) -> tuple[str, np.ndarray, np.ndarray]:
    """Cell name, physical cycle ids (the raw keys) and discharge capacity in Ah."""
    document = DataOnlyUnpickler(io.BytesIO(raw)).load()
    ((name, cell),) = document.items()
    cycles = sorted(cell["dq"])
    capacity_ah = np.array([float(cell["dq"][c]) for c in cycles]) / 1000.0
    return str(name), np.array(cycles, dtype=float), capacity_ah


def cell_capacity(raw: bytes) -> tuple[str, np.ndarray]:
    """Discharge capacity in Ah per cycle for one pickled cell."""
    name, _, capacity = cell_series(raw)
    return name, capacity


def build_cache(
    archive: Path = ARCHIVE,
    output: Path = OUTPUT,
    stride: int | str = sampling.DEFAULT_STRIDE,
) -> int:
    with archive.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != SHA256:
            raise ValueError("archive_checksum_mismatch")
    histories: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as bundle:
        for member in sorted(n for n in bundle.namelist() if n.endswith(".pkl")):
            name, ids, capacity = cell_series(bundle.read(member))
            history = to_history(
                name,
                AMBIENT_C,
                capacity,
                prefix="HUST",
                chemistry="lfp",
                cycle_ids=ids,
                stride=stride,
            )
            histories.append(history.model_dump(mode="json"))
    _, _, info = sampling.thin(np.arange(1.0, 3.0), np.zeros(2), stride)
    meta = {
        **info,
        "source": SOURCE,
        "archive_sha256": SHA256,
        "cycle_id_source": "raw_pickle_keys",
        "reference": "median of the first three discharges",
    }
    sampling.write_cache(output, meta, histories)
    return len(histories)


def load_cache_with_meta(
    path: Path = OUTPUT,
) -> tuple[dict[str, Any], list[BatteryRequest]]:
    if not path.exists():
        return {}, []
    meta, cells = sampling.read_cache(path)
    return meta, [BatteryRequest.model_validate(i) for i in cells]


def load_cache(path: Path = OUTPUT) -> list[BatteryRequest]:
    return load_cache_with_meta(path)[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--stride",
        default=str(sampling.DEFAULT_STRIDE),
        help='fixed physical stride in cycles, or "adaptive" for the legacy diagnostic mode',
    )
    args = parser.parse_args()
    stride: int | str = "adaptive" if args.stride == "adaptive" else int(args.stride)
    output = args.output or (
        LEGACY_OUTPUT
        if stride == "adaptive"
        else ROOT / f"hust/cells-fixed-stride{stride}.json"
    )
    print(f"{build_cache(args.archive, output, stride)} cells written to {output}")


if __name__ == "__main__":
    main()
