#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/4] Python test suite"
python3 -m unittest discover -s tests -v

echo "[2/4] TypeScript/Next.js production build"
cd web
npm run build
cd "$ROOT"

echo "[3/4] Model runtime health"
if curl -fsS --max-time 3 http://127.0.0.1:8891/health >/tmp/aegis-model-health.json; then
  cat /tmp/aegis-model-health.json
else
  echo "Model runtime is not running; start it before live chat testing."
fi

echo "[4/4] Control center source checks"
test -f web/app/components/AegisChat.tsx
test -f web/app/components/PentestChat.tsx
test -f web/app/api/chat/route.ts
test -f web/app/api/pentest/route.ts

echo "AEGIS phases 3-6 build checks complete."
