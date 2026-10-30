# Hardware requirements for production use

This document separates what was **measured** from what is **recommended**. The measurements were taken once, on one machine (section 1). No load testing, fleet-scale runs (hundreds of assets), failover tests, or Windows/macOS/arm64 runs have been done; the recommendations for those cases are engineering estimates with headroom, not test results. Confirm them with a pilot on your own hardware and asset count before going live.

## 1. What was measured

Test bench: laptop with an Intel Core i5-1235U (12 threads), 23 GB RAM, NVMe, Linux x86-64, Python 3.12, CPU only, no GPU.

| Quantity | Value | How it was obtained |
|---|---|---|
| Container image | about 2 GB on disk (434 MB of compressed content) | `docker images` |
| API process memory after start-up and 5 requests | about 373 MB RSS | `/proc/<pid>/status` |
| `/api/battery/example` response | 1–5 ms over a local connection | `curl`, 6 requests |
| Prediction by all models for one window | about 8 ms | `method_experiment`, `latency` field |
| Trained model size | GB ≈ 0.2 MB, GPR ≈ 5 MB, detector and RUL weights bundle about 3 MB | files in `artifacts/` and `metrics.json` |
| Full method comparison (77 HUST cells, 10 processes) | 29 seconds | `method_experiment --workers 10` |
| Local data directory `artifacts/battery-local` | 5.8 GB (NASA, CALB, HUST sources and caches) | `du` |

No GPU is used for training or inference: the image is built with the CPU build of PyTorch.

## 2. Recommendations by role

The numbers in the tables are **recommendations**, except where they repeat the measurements above.

### 2.1. Inference only (dashboard and API), up to a few dozen assets

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 x86-64 cores | 4 cores |
| RAM | 1 GB | 2 GB (the process measured 0.4 GB; the rest is headroom for the OS and container engine) |
| Disk | 5 GB (2 GB image, weights volume, logs) | 20 GB SSD |
| Network | 100 Mbit/s | 1 Gbit/s, plant LAN |
| GPU | not needed | not needed |

One server instance does both ingestion and inference. Headroom for hundreds of assets and thousands of simultaneous clients has **not been measured**.

### 2.2. Retraining (`scripts/train_all.sh`) and experiments

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores | 8–12 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB free | 50 GB SSD if you need all public datasets (5.8 GB) and several weight bundles |

When running experiments in several processes, set `OMP_NUM_THREADS=1`; otherwise BLAS threads oversubscribe the machine, which is how the first method-comparison run took 50 minutes instead of 29 seconds. The 108-cell backtest takes about 35 CPU-minutes; it has not been re-run since the stride fix.

### 2.3. Building from source

A C++20 compiler (GCC or Clang), CMake, Ninja, Python 3.12, 4 GB RAM, and about 10 GB of disk for `.venv` (1.5 GB here) and the build. In the container image the multi-stage build does all of this; the production host needs no compiler.

## 3. Software environment

- Docker Engine or Docker Desktop with Compose v2. Tested on Linux x86-64 (CI and locally).
- arm64: the same Dockerfile builds, but it was not tested here.
- Windows and macOS (Docker Desktop): not tested.
- The container runs without root (uid 10001) with `read_only`, `cap_drop: ALL` and `no-new-privileges`. Weights and data live in the named volume `argus-data`.
- Port 8000, bound to `127.0.0.1` by default.

## 4. Conditions for a production environment

The prototype is **not ready** to be published to a network directly. The following has to be done outside the software.

1. **The API has no authentication.** Do not expose the port. Put a reverse proxy with TLS and authentication in front of it (or restrict it by network policy) before changing the bind address in `docker-compose.yml`.
2. **Data source.** The dashboard shows a synthetic generator and public laboratory data. There are no adapters for real telemetry (OCPP, Modbus, CAN, vendor APIs) and no measurement of false alarms on real assets.
3. **Storage and backups.** Weights and results sit in the `argus-data` volume: schedule regular backups of the volume and keep previous weight bundles (new bundles are activated only after validation and old ones are kept).
4. **Single instance.** There is no built-in replication, load balancing or failover. For availability requirements, rely on automatic restart (`restart: unless-stopped` is set in Compose) and external monitoring of `/api/health`.
5. **Time and logs.** Keep the host clock synchronised (NTP); collect and rotate the container logs.
6. **Scope of validity.** The metrics come from LFP cells in the laboratory; transfer to EV packs, UAVs, scooters and power banks has not been checked. Equipment from real customers needs its own validation.

## 5. How to check on your own hardware

```bash
docker compose up -d --build
docker compose exec argus bash scripts/train_all.sh
docker compose restart argus
bash scripts/docker_smoke.sh
docker stats --no-stream
```

Record memory and CPU use at your asset count and compare it with table 2.1 before growing the fleet.
