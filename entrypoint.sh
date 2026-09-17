#!/bin/sh
set -e

echo "[entrypoint] environment=${ENVIRONMENT:-development} data_dir=${DATA_DIR:-/data}"

# Create tables if they do not exist, then seed reference data.
# Both steps are idempotent and safe to run on every container start.
python -m app.db.init_db

exec "$@"
