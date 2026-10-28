# Published measured battery histories

The landing page offers four NASA PCoE laboratory cells without requiring personal measurements: **B0005, B0006, B0007 and B0018**. Select the cell, choose how many observed discharge tests to include, and select **Load measured NASA history**. The default is the first 40 tests; the full available trajectory is not passed to the assessment.

These are measured individual Li-ion cells, not generated curves or full electric-vehicle battery packs. The application labels their scope and source, uses a discharge-test index, leaves current SOC unknown, and does not produce calendar months. Use the existing synthetic EV example separately to understand the pack input format.

## Source and local installation

- Official source and requested attribution: [NASA Prognostics Data Repository, Batteries](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/).
- Dataset description: [NASA Li-ion Battery Aging Datasets](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets).
- Citation: B. Saha and K. Goebel (2007), “Battery Data Set”, NASA Ames Prognostics Center of Excellence.
- The NASA catalogue does not specify a dataset license. This integration keeps downloads and processed measurements in an ignored local research cache; it does not package them under this repository's software license or redistribute them with the code.

One-time preparation, from the repository root after installing the Python requirements:

```bash
PYTHONPATH="$PWD/python" .venv/bin/python -m argus.battery.public_data --download
bash scripts/run_dashboard.sh
```

The download is about 210 MB. The URL is fixed to the mirror linked by the official NASA page. No vehicle data or uploaded files are transmitted. Already downloaded archives are reused. To use an existing archive without network access:

```bash
PYTHONPATH="$PWD/python" .venv/bin/python -m argus.battery.public_data --archive /path/to/nasa-source.zip
```

The installer validates the entire archive and each selected MAT file, imports the original discharge `Capacity` measurements in Ah, checks a single ambient-temperature condition per selected cell, and records provenance. It refuses changed archives or conflicting existing cache files rather than silently replacing them. Original source measurements stay in `artifacts/battery-local/public-nasa/`, excluded from Git. Exported assessments retain attribution and checksums.

## Pinned source checksums

| File | SHA-256 |
|---|---|
| Original archive | `82302a7db4fc1b34e0b6676326610438d43b816bdf11a69d1d012a464ef2f92e` |
| B0005.mat | `0eae4585baf3f200c09fe24c5ab884f1889679fc75206ca1aa19da704104f0b0` |
| B0006.mat | `fa818ab4db5db8ab21e910b6dd6c3e20d3761bb9672089e1a4de8f96074616c5` |
| B0007.mat | `d022afa086efaf54ab5b63f05220f5be178c8027e2fa8d68589db0e85a441a3b` |
| B0018.mat | `d1e6c923a43ea1c9666b3a90bbb521757a067fd60b4d17dbfaa49c50b179da69` |

## A concrete measured result

With the first 40 discharge tests of **B0018**, capacity-based SOH is **83.8%** against the 2 Ah rated reference. The current trend method produces a descriptive **32–43.5 additional discharge-test** interval to the configured 70% capacity threshold. This is a conditional extrapolation, not a measured future lifetime, confidence guarantee or a prognosis for an EV pack. Other cells or prefixes may return no numerical projection when the trend checks fail.

Profiles are not interchangeable: the source describes different discharge cutoff conditions for different cells. No pooling of these four cells, ML training or field validation is implied by this interface. The existing trend method and its refusal rules are described in [BATTERY.md](BATTERY.md).

## API

| Route | Result |
|---|---|
| `GET /api/battery/datasets` | Four fixed identifiers and local availability |
| `GET /api/battery/datasets/nasa-B0018?observations=40` | Observed-prefix request and source metadata |
| `POST /api/battery/analyze` | Checks the supplied published measurements against the local cache before retaining the source label |

Only these fixed dataset identifiers are accepted; clients cannot provide filesystem paths or download URLs. A missing cache returns 503. Prefix length is bounded to 8–2,000 and capped by the available history. Edits to the published capacity measurements or a change to pack/EFC semantics cannot retain the verified cache label. Cache hashes detect accidental modification; they are not digital signatures.
