#!/usr/bin/env bash
set -euo pipefail

platform="${AEGIS_BROWSER_PLATFORM:-wayland}"
launch_env=(env)

case "$platform" in
  wayland)
    if [[ -z "${WAYLAND_DISPLAY:-}" || -z "${XDG_RUNTIME_DIR:-}" ]]; then
      echo "WAYLAND_DISPLAY and XDG_RUNTIME_DIR are required for the native Wayland browser" >&2
      exit 2
    fi
    launch_env+=(DISPLAY=)
    ozone_platform="wayland"
    ;;
  x11)
    if [[ -z "${DISPLAY:-}" ]]; then
      echo "DISPLAY is required for the X11/XWayland browser" >&2
      exit 2
    fi
    launch_env+=(WAYLAND_DISPLAY=)
    ozone_platform="x11"
    ;;
  *)
    echo "AEGIS_BROWSER_PLATFORM must be wayland or x11" >&2
    exit 2
    ;;
esac

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
  "--ozone-platform=${ozone_platform}"
  "--disable-gpu"
  "--disable-dev-shm-usage"
  "--disable-background-networking"
  "--disable-component-update"
  "--disable-default-apps"
  "--disable-extensions"
  "--disable-sync"
  "--force-renderer-accessibility"
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
exec "${launch_env[@]}" "$browser" "${args[@]}" "$url"
