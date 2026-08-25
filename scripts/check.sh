#!/usr/bin/env bash
set -euo pipefail

echo "Building all application images..."
docker compose build backend agent frontend

echo "Running backend tests..."
docker compose run --rm backend pytest -q

echo "Type-checking Pi agent service..."
docker compose run --rm agent npm run typecheck

echo "Checks complete."
