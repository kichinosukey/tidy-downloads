#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

export LOCAL_LLM_MODEL="${LOCAL_LLM_MODEL:-apple-foundationmodel}"
export LOCAL_LLM_BASE_URL="${LOCAL_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export LOCAL_LLM_API_KEY="${LOCAL_LLM_API_KEY:-not-needed}"
export LOCAL_LLM_API_MODE="${LOCAL_LLM_API_MODE:-chat_completions}"

"${REPO_ROOT}/scripts/ensure_apfel_serve.sh"

if command -v tidy-downloads >/dev/null 2>&1; then
  exec tidy-downloads "$@"
fi

if command -v uv >/dev/null 2>&1 && [[ -f "${REPO_ROOT}/pyproject.toml" ]]; then
  exec uv run --directory "${REPO_ROOT}" tidy-downloads "$@"
fi

PYTHON="${REPO_ROOT}/.venv/bin/python"
if [[ -x "${PYTHON}" ]]; then
  exec "${PYTHON}" -m tidy_downloads "$@"
fi

exec "$(command -v python3)" -m tidy_downloads "$@"
