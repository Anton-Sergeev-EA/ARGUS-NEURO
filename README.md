# ARGUS-NEURO

**Predictive health intelligence for power-electronics fleets — marine power/control systems and unmanned aerial power systems, monitored by one platform.**

[Русская версия README](README.ru.md) · [Architecture](#architecture) · [Quickstart](#quickstart) · [ML/DL design](#two-tier-mldl-design) · [Author](#author)

---

## Why one platform for two domains

A shipboard frequency converter driving a steering gear and a UAV power-distribution unit feeding a flight controller look, on paper, like unrelated pieces of hardware. Electrically they are the same kind of object: a power-electronic stage with voltage, current, temperature, vibration and frequency telemetry, that degrades through a small, well-understood set of failure modes — overheating, bearing/insulation wear, voltage sag, frequency drift — long before it actually fails.

**ARGUS-NEURO** is a single condition-monitoring and predictive-maintenance stack built around that observation. Instead of two bespoke diagnostic tools for two industries, it is one asset-agnostic pipeline — signal processing, classical ML, deep learning, and a live dashboard — validated against synthetic but physically-grounded telemetry for both a marine converter/drive asset class and a UAV power-distribution-unit asset class.

## Key capabilities

- **Two-tier anomaly detection.** A fast classical model (Isolation Forest) screens instantaneous waveform spectra at the edge; a deep sequence model (LSTM autoencoder) judges slower multivariate trends that only emerge over time.
- **Remaining Useful Life (RUL) estimation.** A GRU regressor turns a rolling telemetry window into an operationally actionable "hours until service" number, not just a binary alarm.
- **Native C++20 signal core.** RMS, crest factor, kurtosis, skewness, and a hand-written radix-2 FFT for spectral features — exposed to Python via `pybind11`, with a pure-NumPy fallback so the pipeline still runs without a C++ toolchain.
- **ONNX export.** Both deep models export to ONNX so they can be served from a C++ inference loop (ONNX Runtime) on the same edge hardware that runs the native feature core, without a Python interpreter in the deployed path.
- **Live web console.** A dependency-free HTML/CSS/JS dashboard streams fleet health over WebSocket in real time, with a client-side offline-demo fallback so it is also a meaningful standalone artifact.
- **Bilingual, reproducible, tested.** Every model is trained from a synthetic-but-realistic simulator (so the pipeline is exercised end to end without proprietary data), covered by unit tests, and wired into CI.

## Architecture

```mermaid
flowchart LR
    subgraph Edge["Edge / control cabinet"]
        WF["Raw waveform\n(voltage / current / vibration)"]
        CPP["argus_core (C++20)\nRMS · kurtosis · FFT features"]
        T1["Tier 1: Isolation Forest\n(SpectralBaselineDetector)"]
        WF --> CPP --> T1
    end

    subgraph Trend["Trend engine"]
        TEL["Multivariate telemetry\n(voltage, current, temp,\nvibration, freq, load)"]
        AE["Tier 2a: LSTM Autoencoder\nreconstruction-error anomaly score"]
        RUL["Tier 2b: GRU RUL Regressor\nremaining useful life"]
        TEL --> AE
        TEL --> RUL
    end

    T1 --> FUSE["HealthInferenceEngine\nscore fusion -> 0-100 health index"]
    AE --> FUSE
    RUL --> FUSE

    FUSE --> API["FastAPI + WebSocket backend"]
    API --> DASH["ARGUS-NEURO dashboard\n(HTML / CSS / JS, live gauges + sparklines)"]

    ONNX["ONNX export\n(autoencoder.onnx, rul_predictor.onnx)"]
    AE -. torch.onnx.export .-> ONNX
    RUL -. torch.onnx.export .-> ONNX
    ONNX -. "ONNX Runtime (C++)" .-> Edge
```

## Two-tier ML/DL design

The cascade is a deliberate architectural choice, not two models bolted together for coverage:

| Tier | Model | Input | Why this tier |
|---|---|---|---|
| 1 | `SpectralBaselineDetector` (Isolation Forest, scikit-learn) | 11-dim feature vector from one raw waveform window (via `argus_core`) | Cheap enough to run continuously on constrained edge hardware; no history required; catches sudden, spectrally-obvious faults immediately. |
| 2a | `LSTMAutoencoder` (PyTorch) | Rolling window of 6-channel telemetry, trained unsupervised on healthy data only | Learns what *normal* multivariate behaviour looks like over time — catches slow drifts a single instant can't reveal, without needing labelled failures (which real fleets rarely have). |
| 2b | `RULRegressorGRU` (PyTorch) | Same rolling window, trained on the simulator's labelled degradation trajectories | Converts "something looks off" into "how long until this needs maintenance" — the number that actually drives a scheduling decision. |

`HealthInferenceEngine` (`python/argus/inference/engine.py`) fuses all three scores into one 0–100 health index. If no trained artifacts are found, it degrades gracefully to a transparent heuristic so the system is runnable before the first training run.

## Repository structure

```
argus-neuro/
├── cpp_core/                # C++20 signal-processing core + pybind11 bindings
│   ├── include/argus_core/  # signal_features.hpp
│   ├── src/                 # signal_features.cpp, bindings.cpp
│   └── tests/                # dependency-free native unit tests
├── python/
│   ├── argus/
│   │   ├── simulator/       # synthetic telemetry + waveform generator
│   │   ├── features/        # native-core-or-NumPy feature extraction
│   │   ├── models/          # LSTMAutoencoder, RULRegressorGRU, SpectralBaselineDetector
│   │   ├── training/        # dataset building + training entry points
│   │   ├── export/          # ONNX export
│   │   ├── inference/       # HealthInferenceEngine (runtime fusion)
│   │   └── api/              # FastAPI + WebSocket backend
│   ├── tests/                # pytest suite
│   └── requirements.txt
├── web/dashboard/            # HTML/CSS/JS live console (no external dependencies)
├── artifacts/                 # pre-trained demo weights (regenerate via scripts/train_all.sh)
├── scripts/                   # setup / build / train / run helpers
├── .github/workflows/ci.yml   # build + test on every push
├── CMakeLists.txt
└── README.md / README.ru.md
```

## Tech stack

| Layer | Technology |
|---|---|
| Native core | C++20 (concepts, `<span>`, `constexpr`), CMake, pybind11 |
| ML / DL | Python 3.11, PyTorch (LSTM / GRU), scikit-learn (Isolation Forest), ONNX / `torch.onnx` (dynamo exporter) |
| Backend | FastAPI, WebSockets, Uvicorn (asyncio) |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (Canvas-based gauges & sparklines, no external CDN) |
| Testing / CI | pytest, dependency-free C++ asserts, GitHub Actions |

## Quickstart

```bash
git clone <this-repo> argus-neuro && cd argus-neuro

# 1. Install Python deps + build the native C++ core (creates ./build)
bash scripts/setup_env.sh

# 2. Point Python at both the package and the compiled extension
export PYTHONPATH="$PWD/python:$PWD/build/cpp_core"

# 3. (Optional) retrain everything from scratch -- pre-trained demo
#    weights already ship in ./artifacts
bash scripts/train_all.sh

# 4. Run the tests
cd python && python -m pytest -v && cd ..

# 5. Launch the live dashboard
bash scripts/run_dashboard.sh
# -> open http://localhost:8000/
```

The dashboard also works if you open `web/dashboard/index.html` directly without a backend: it detects the missing WebSocket connection and switches to a self-contained client-side demo simulation.

## Testing

- `cpp_core/tests/test_signal_features.cpp` — dependency-free asserts covering RMS/mean of known signals, FFT-based dominant-frequency detection on a synthetic sine wave, and spectral-energy sanity checks.
- `python/tests/` — simulator sanity checks, feature-extraction correctness (validated against a known sine wave), model forward-pass shapes, a training-step-reduces-loss regression test, and Isolation Forest separation between normal and extreme data.
- `.github/workflows/ci.yml` builds the native core, runs its tests, then runs the full pytest suite against the compiled extension.

## Roadmap

- [ ] Attention-based sequence model (Transformer encoder) as an alternative tier-2 backbone.
- [ ] C++ ONNX Runtime inference bridge (sketching the `Edge` box in the diagram above into actual code).
- [ ] Multi-asset fleet-level risk aggregation and maintenance scheduling optimizer.
- [ ] Historical telemetry ingestion adapters (CSV/OPC-UA/MQTT) to replace the simulator with real fleet data.

## Author

**Сергеев Антон Валентинович** (Sergeev Anton Valentinovich)
Email: [avsergeev1981@gmail.com](mailto:avsergeev1981@gmail.com)

## License

See [LICENSE](LICENSE) — all rights reserved, provided for evaluation and demonstration.
