#!/usr/bin/env bash
set -euo pipefail

INSTALL_TAG="${TIDY_DOWNLOADS_INSTALL_TAG:-v0.1.1}"
GITHUB_REPO="${TIDY_DOWNLOADS_GITHUB_REPO:-kichinosukey/tidy-downloads}"
WITH_LAUNCHD=0

usage() {
  cat <<EOF
Usage: install.sh [--with-launchd]

Installs tidy-downloads via uv tool install (macOS 26+, Homebrew, apfel required).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-launchd)
      WITH_LAUNCHD=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

die() {
  echo "install.sh: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  die "tidy-downloads requires macOS (Darwin)"
fi

require_cmd curl

if ! command -v brew >/dev/null 2>&1; then
  die "Homebrew is required. See https://brew.sh/"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "installing uv via Homebrew..."
  brew install uv
fi

if ! command -v apfel >/dev/null 2>&1; then
  echo "installing apfel via Homebrew..."
  brew install apfel
fi

if ! apfel --model-info 2>/dev/null | grep -Eq 'available:[[:space:]]*yes'; then
  echo "apfel --model-info:" >&2
  apfel --model-info >&2 || true
  die "apfel model not available (need macOS 26+ with Apple Intelligence enabled)."
fi

UV_SPEC="git+https://github.com/${GITHUB_REPO}.git@${INSTALL_TAG}"
echo "installing tidy-downloads from ${UV_SPEC} ..."
uv tool install --force "${UV_SPEC}"

export PATH="${HOME}/.local/bin:${PATH}"
if ! command -v tidy-downloads >/dev/null 2>&1; then
  die "tidy-downloads not on PATH. Add to your shell profile: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

tidy-downloads plan --help >/dev/null
echo "tidy-downloads installed successfully."
echo "Executables are in ~/.local/bin (add to PATH if needed)."

if [[ "${WITH_LAUNCHD}" -eq 1 ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
  PLIST_SRC="${REPO_ROOT}/launchd/com.tidy-downloads.fastlane.plist"
  PLIST_DST="${HOME}/Library/LaunchAgents/com.tidy-downloads.fastlane.plist"
  sed \
    -e "s|REPLACE_WITH_REPO_ROOT|${REPO_ROOT}|g" \
    -e "s|/Users/REPLACE_ME|${HOME}|g" \
    "${PLIST_SRC}" >"${PLIST_DST}"
  launchctl bootout "gui/$(id -u)/com.tidy-downloads.fastlane" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${PLIST_DST}"
  launchctl enable "gui/$(id -u)/com.tidy-downloads.fastlane"
  echo "launchd job installed: ${PLIST_DST}"
fi
