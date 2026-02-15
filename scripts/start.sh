#!/usr/bin/env bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting Uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 10000
