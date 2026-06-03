#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${APFEL_BASE_URL:-http://127.0.0.1:11434/v1}"
MODEL="${APFEL_MODEL:-apple-foundationmodel}"
WAIT_SECONDS="${APFEL_SERVE_WAIT_SECONDS:-45}"
PIDFILE="${APFEL_SERVE_PIDFILE:-/tmp/tidy-downloads-apfel-serve.pid}"
LOGFILE="${APFEL_SERVE_LOGFILE:-/tmp/tidy-downloads-apfel-serve.log}"

models_endpoint() {
  printf '%s\n' "${BASE_URL%/}/models"
}

is_ready() {
  curl -sf "$(models_endpoint)" 2>/dev/null | grep -q "\"${MODEL}\""
}

started_by_script=0

cleanup_stale_pid() {
  if [[ ! -f "${PIDFILE}" ]]; then
    return
  fi
  local pid
  pid="$(cat "${PIDFILE}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    return
  fi
  rm -f "${PIDFILE}"
}

if is_ready; then
  exit 0
fi

cleanup_stale_pid

if [[ -f "${PIDFILE}" ]]; then
  for _ in $(seq 1 "${WAIT_SECONDS}"); do
    if is_ready; then
      exit 0
    fi
    sleep 1
  done
fi

nohup apfel --serve >>"${LOGFILE}" 2>&1 &
echo "$!" >"${PIDFILE}"
started_by_script=1

for _ in $(seq 1 "${WAIT_SECONDS}"); do
  if is_ready; then
    exit 0
  fi
  sleep 1
done

if [[ "${started_by_script}" -eq 1 ]]; then
  pid="$(cat "${PIDFILE}" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]]; then
    kill "${pid}" 2>/dev/null || true
  fi
  rm -f "${PIDFILE}"
fi

echo "apfel serve did not become ready at ${BASE_URL} (model=${MODEL})" >&2
echo "see ${LOGFILE}" >&2
exit 1
