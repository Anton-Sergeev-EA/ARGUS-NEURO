#!/usr/bin/env bash
# Runs the full ML/DL pipeline: baseline + autoencoder training, RUL
# regressor training, then ONNX export. Writes everything to ./artifacts.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH="${PWD}/python:${PWD}/build/cpp_core:${PYTHONPATH:-}"

python3 -m argus.training.train_anomaly
python3 -m argus.training.train_rul
python3 -m argus.export.export_onnx
