FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY schema.sql .
COPY scripts/import_songs.py ./scripts/import_songs.py
COPY data/songs/ ./data/songs/
RUN python scripts/import_songs.py


FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY app/ app/
COPY scripts/ scripts/
COPY --from=builder /build/data/lyrics.db data/lyrics.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]