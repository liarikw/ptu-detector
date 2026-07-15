FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY public/ ./public/

ENV PYTHONUNBUFFERED=1

# HF Spaces uses 7860; Fly/Railway/Render set PORT.
CMD sh -c 'uvicorn api.index:app --host 0.0.0.0 --port ${PORT:-7860}'
