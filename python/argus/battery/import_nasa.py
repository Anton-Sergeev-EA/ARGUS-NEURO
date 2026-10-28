"""Convert an official local NASA archive without guessing physical battery IDs."""

from __future__ import annotations
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from argus.battery.data import import_nasa_mat

SOURCE_URL = "https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip"


def convert(archive: Path, output: Path, raw_dir: Path) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    selected = {}
    protocols = {}
    with zipfile.ZipFile(archive) as outer:
        # Later full-life archives supersede the explicitly partial P1 archive.
        for name in sorted(outer.namelist()):
            if not name.endswith(".zip"):
                continue
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                for member in inner.namelist():
                    if member.lower().endswith(".mat"):
                        filename = Path(member).name
                        if filename.startswith("B") and len(filename) <= 20:
                            selected[filename] = inner.read(member)
                    elif member.lower().endswith(".txt"):
                        protocols[name + "/" + Path(member).name] = inner.read(
                            member
                        ).decode("utf-8", errors="replace")
    histories = []
    for name, content in sorted(selected.items()):
        path = raw_dir / name
        path.write_bytes(content)
        histories.append(import_nasa_mat(path))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(histories, indent=2, allow_nan=False))
    manifest = {
        "source_url": SOURCE_URL,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "dataset_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "physical_batteries": len(histories),
        "protocol_readmes": protocols,
        "limits": [
            "measured_cells_not_ev_packs",
            "axis_is_discharge_test_index_not_efc",
            "varied_temperature_and_cutoff_protocols",
        ],
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert official NASA measured battery cells"
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()
    result = convert(args.archive, args.output, args.raw_dir)
    print(result["physical_batteries"])


if __name__ == "__main__":
    main()
