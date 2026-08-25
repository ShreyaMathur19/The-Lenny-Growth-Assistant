#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "[1/5] Starting PostgreSQL and Ollama..."
docker compose up -d postgres ollama

echo "[2/5] Pulling local chat + embedding models..."
docker compose --profile setup run --rm ollama-init

echo "[3/5] Building backend and applying migrations..."
docker compose build backend agent frontend
docker compose run --rm backend alembic upgrade head

if [ ! -f data/transcripts/.downloaded ]; then
  echo "[4/5] Downloading Lenny transcript archive..."
  docker compose run --rm backend python scripts/fetch_transcripts.py
  touch data/transcripts/.downloaded
else
  echo "[4/5] Transcript archive already downloaded."
fi

echo "[5/5] Indexing transcripts with Ollama embeddings..."
docker compose run --rm backend python scripts/ingest_transcripts.py --replace

echo "Bootstrap complete. Start the app with: docker compose up --build"
