# Dockerfile для backend
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для аудио
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Копируем backend
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY config/ ./config/

# Создаем директории для данных
RUN mkdir -p data/raw data/normalized data/denoised data/vad_segments data/transcriptions

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
