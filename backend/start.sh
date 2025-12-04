#!/bin/bash
set -e

echo "Running database migrations..."
# Try to run migrations, but don't fail if they error (database might already be initialized)
alembic upgrade head 2>&1 || echo "Warning: Migrations failed or already applied, continuing..."

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
