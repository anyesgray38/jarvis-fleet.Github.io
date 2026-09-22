#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v tailscale >/dev/null 2>&1 || { echo "Tailscale is required."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker is required."; exit 1; }

tailscale status >/dev/null 2>&1 || {
  echo "Tailscale is not connected. Run: sudo tailscale up"
  exit 1
}

if [[ ! -f deploy/.env ]]; then
  cp deploy/.env.example deploy/.env
fi

# Never accept the checked-in template value as a real credential.
if ! grep -q '^AEGIS_FLEET_SECRET=' deploy/.env \
  || grep -Eq '^AEGIS_FLEET_SECRET=(|replace-with-a-long-random-secret)$' deploy/.env; then
  secret="$(dd if=/dev/urandom bs=32 count=1 2>/dev/null | od -An -tx1 | tr -d ' \n')"
  if grep -q '^AEGIS_FLEET_SECRET=' deploy/.env; then
    sed -i "s/^AEGIS_FLEET_SECRET=.*/AEGIS_FLEET_SECRET=${secret}/" deploy/.env
  else
    printf '\nAEGIS_FLEET_SECRET=%s\n' "$secret" >> deploy/.env
  fi
fi

# The AEGIS web server listens only on localhost. Tailscale Serve is the
# sole ingress and is private to the tailnet (never use `tailscale funnel`).
docker compose --env-file deploy/.env -f deploy/compose.yml up -d --build

tailscale serve --bg 3000

echo
echo "AEGIS is running locally and served only to the Tailscale tailnet."
tailscale serve status
printf '\nTailscale address:\n'
tailscale ip -4
printf '\nOpen the HTTPS URL reported by `tailscale serve status` on your iPhone.\n'
