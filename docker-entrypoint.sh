#!/bin/sh
set -eu

mkdir -p /app/data /app/logs

run_auto_pipeline_loop() {
  interval="${AUTO_PIPELINE_CHECK_SECONDS:-60}"
  echo "[entrypoint] auto_pipeline loop enabled; check interval: ${interval}s"

  while true; do
    PYTHONIOENCODING=utf-8 python /app/auto_pipeline.py || true
    sleep "${interval}"
  done
}

run_auto_pipeline_loop &

exec streamlit run /app/ui/app.py \
  --server.port="${STREAMLIT_SERVER_PORT:-8501}" \
  --server.address="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}"
