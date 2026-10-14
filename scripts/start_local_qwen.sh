#!/usr/bin/env bash
# Foreground, loopback-only test server; does not change AWS or Compose settings.
set -euo pipefail

qwen_server="${AEGIS_LLAMA_SERVER:-$HOME/.local/opt/llama-b11429/llama-server}"
qwen_weights="${AEGIS_SMALL_QWEN_FILE:-$HOME/.local/share/aegis/models/qwen3.5-0.8b/Qwen3.5-0.8B-Q4_0.gguf}"
qwen_alias="${AEGIS_SMALL_QWEN_ALIAS:-aegis-qwen3.5-0.8b-q4_0}"

if [[ ! -x "$qwen_server" || ! -f "$qwen_weights" ]]; then
  echo 'Local Qwen installation is incomplete. See docs/local-qwen.md.' >&2
  exit 1
fi

exec "$qwen_server" \
  --model "$qwen_weights" \
  --alias "$qwen_alias" \
  --host 127.0.0.1 --port 8081 --cors-origins localhost --no-agent \
  --ctx-size 2048 --parallel 1 \
  --threads 2 --threads-batch 2 --threads-http 2 \
  --batch-size 128 --ubatch-size 128 \
  --n-gpu-layers 0 --reasoning-budget 0 --n-predict 256 --offline
