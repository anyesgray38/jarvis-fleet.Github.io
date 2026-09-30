#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DISPLAY:-}" ]]; then
  echo "DISPLAY is required for the governed X11 browser" >&2
  exit 2
fi

browser="${AEGIS_CHROMIUM_BIN:-}"
if [[ -z "$browser" ]]; then
  if command -v chromium >/dev/null 2>&1; then
    browser="$(command -v chromium)"
  elif command -v google-chrome >/dev/null 2>&1; then
    browser="$(command -v google-chrome)"
  else
    browser="${HOME}/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
  fi
fi

if [[ ! -x "$browser" ]]; then
  echo "Chromium executable not found: $browser" >&2
  exit 1
fi

profile="${AEGIS_CONTROL_BROWSER_PROFILE:-${XDG_RUNTIME_DIR:-/tmp}/aegis-control-browser}"
port="${AEGIS_BROWSER_CDP_PORT:-9222}"
window_size="${AEGIS_BROWSER_WINDOW_SIZE:-1200,800}"
mkdir -p "$profile"

args=(
  "--ozone-platform=x11"
  "--disable-gpu"
  "--disable-dev-shm-usage"
  "--no-first-run"
  "--no-default-browser-check"
  "--window-size=${window_size}"
  "--remote-debugging-port=${port}"
  "--user-data-dir=${profile}"
)
if [[ "${AEGIS_BROWSER_NO_SANDBOX:-0}" == "1" ]]; then
  args+=("--no-sandbox")
fi

url="${1:-about:blank}"
exec env WAYLAND_DISPLAY= "$browser" "${args[@]}" "$url"
