# syntax=docker/dockerfile:1
# ARGUS-NEURO in one image: builds the C++20 core and the pybind11 module, then serves the
# dashboard and API on port 8000. CPU only; works on linux/amd64 and linux/arm64.

FROM python:3.12-slim-bookworm AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY python/requirements.txt python/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu \
    && /opt/venv/bin/pip install --no-cache-dir -r python/requirements.txt
COPY CMakeLists.txt .
COPY cpp_core cpp_core
COPY scripts/build_cpp_core.sh scripts/build_cpp_core.sh
ENV ARGUS_PYTHON=/opt/venv/bin/python
RUN bash scripts/build_cpp_core.sh && ctest --test-dir build --output-on-failure \
    && mkdir /native && cp build/cpp_core/argus_core*.so /native/

FROM python:3.12-slim-bookworm AS runtime
RUN useradd --system --uid 10001 --create-home argus
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /native /app/native
COPY python/argus python/argus
COPY web/dashboard web/dashboard
COPY scripts/train_all.sh scripts/train_all.sh
COPY artifacts artifacts
# Trained bundles, downloaded public datasets and saved reports live under artifacts/;
# mount a volume on it (compose does) so they survive container re-creation.
RUN mkdir -p artifacts/battery-local && chown -R argus:argus artifacts
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/python:/app/native \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARGUS_PYTHON=/opt/venv/bin/python \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1
USER argus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "argus.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
