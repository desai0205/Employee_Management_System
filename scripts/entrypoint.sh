#!/bin/sh
set -eu

alembic upgrade head

if [ "${1:-api}" = "worker" ]; then
  exec arq app.workers.settings.WorkerSettings
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
