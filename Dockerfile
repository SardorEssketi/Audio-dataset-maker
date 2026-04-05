# Dockerfile for backend

FROM python:3.11-slim AS builder

WORKDIR /app

# Build deps: needed for packages that compile native extensions (e.g. webrtcvad on Linux).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .

# Install deps into a venv so we can copy it into the runtime image.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.5.1 \
        torchaudio==2.5.1 \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-prod.txt


FROM python:3.11-slim

WORKDIR /app

# Runtime system deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY config/ ./config/

# Runtime dirs (data is usually mounted via docker-compose volume)
RUN mkdir -p data/raw data/normalized data/denoised data/vad_segments data/transcriptions

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]

