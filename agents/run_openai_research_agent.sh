#!/usr/bin/env bash
set -Eeuo pipefail

# Create a reusable OpenAI Agent definition, then start a streamed research
# session from that definition. The API key is read from deploy/.env and is
# never printed.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AEGIS_ENV_FILE:-$ROOT/deploy/.env}"
API_BASE="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
MESSAGE="${*:-Research the latest developments in OpenAI hosted Agents API web search and summarize the findings with source links.}"
AGENT_ENVIRONMENT="${OPENAI_AGENT_ENVIRONMENT:-openai_hosted}"
INPUT_FILE_ID="${OPENAI_INPUT_FILE_ID:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing credential file: $ENV_FILE" >&2
  exit 1
fi

# Read only the named value; do not source the file as shell code.
OPENAI_API_KEY="$(python3 - "$ENV_FILE" <<'PY'
import sys
from pathlib import Path

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if line.startswith("OPENAI_API_KEY="):
        print(line.split("=", 1)[1].strip().strip("\"'"))
        break
PY
)"
if [[ -z "$OPENAI_API_KEY" ]]; then
  echo "OPENAI_API_KEY is missing from $ENV_FILE" >&2
  exit 1
fi

PROJECT_ID="${OPENAI_PROJECT_ID:-$(python3 - "$ENV_FILE" <<'PY'
import sys
from pathlib import Path

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if line.startswith("OPENAI_PROJECT_ID="):
        print(line.split("=", 1)[1].strip().strip("\"'"))
        break
PY
)}"
PROJECT_ID="${PROJECT_ID:-proj_pHyP61mVdJm7ZhODMpglh2wI}"

AUTH_HEADER="Authorization: Bearer $OPENAI_API_KEY"
PROJECT_HEADER="OpenAI-Project: $PROJECT_ID"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

AGENT_ID="${OPENAI_AGENT_ID:-}"
agent_payload="$TMP_DIR/agent.json"
cat >"$agent_payload" <<'JSON'
{
  "tools": [
    {
      "type": "web_search",
      "mode": "live",
      "context_size": "medium",
      "allowed_domains": null,
      "location": null
    }
  ],
  "multi_agent": {"enabled": false},
  "name": "New agent",
  "model": "gpt-6-astra",
  "instructions": "",
  "service_tier": "default",
  "reasoning": {"effort": "medium", "summary": "auto"},
  "text": {"format": {"type": "text"}, "verbosity": "medium"}
}
JSON

if [[ -z "$AGENT_ID" ]]; then
  agent_response="$TMP_DIR/agent-response.json"
  if ! curl --silent --show-error --fail-with-body \
    -X POST "$API_BASE/agents" \
    -H "$AUTH_HEADER" \
    -H "$PROJECT_HEADER" \
    -H "OpenAI-Beta: agents=v1" \
    -H "Content-Type: application/json" \
    --data-binary "@$agent_payload" \
    >"$agent_response"; then
    python3 - "$agent_response" <<'PY' >&2
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        body = json.load(handle)
    error = body.get("error", body)
    print(f"Agent creation failed: {error.get('message', error)}")
except Exception:
    print("Agent creation failed; the API returned a non-JSON error.")
PY
    exit 1
  fi

  AGENT_ID="$(python3 - "$agent_response" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    body = json.load(handle)
agent_id = body.get("id")
if not agent_id:
    raise SystemExit("Agent creation response did not contain an id")
print(agent_id)
PY
)"
fi
printf 'agent_id=%s\n' "$AGENT_ID"

session_payload="$TMP_DIR/session.json"
python3 - "$AGENT_ID" "$AGENT_ENVIRONMENT" "$INPUT_FILE_ID" "$MESSAGE" "$session_payload" <<'PY'
import json
import sys

agent_id, environment, input_file_id, message, output = sys.argv[1:]
payload = {
    "agent_id": agent_id,
    "environment": {"type": environment},
    "input": message,
    "stream": True,
}
if input_file_id:
    if environment != "openai_hosted":
        raise SystemExit("OPENAI_INPUT_FILE_ID requires OPENAI_AGENT_ENVIRONMENT=openai_hosted")
    payload["environment"]["files"] = [{
        "type": "file_id",
        "file_id": input_file_id,
        "path": "/workspace/input/research.md",
    }]
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY

printf 'session_events:\n'
curl --no-buffer --silent --show-error --fail-with-body \
  -X POST "$API_BASE/agents/sessions" \
  -H "$AUTH_HEADER" \
  -H "$PROJECT_HEADER" \
  -H "OpenAI-Beta: agents=v1" \
  -H "Content-Type: application/json" \
  --data-binary "@$session_payload" \
  | python3 -c '
import json
import sys

event_name = ""
session_id = None
failed = False

for raw in sys.stdin:
    line = raw.rstrip("\\n")
    if line.startswith("event:"):
        event_name = line.split(":", 1)[1].strip()
        print(f"[event] {event_name}", flush=True)
        continue
    if not line.startswith("data:"):
        continue
    data = line.split(":", 1)[1].strip()
    if data == "[DONE]":
        continue
    try:
        body = json.loads(data)
    except json.JSONDecodeError:
        print(data, flush=True)
        continue
    session = body.get("session")
    session_id = session_id or body.get("session_id") or body.get("id")
    if isinstance(session, dict):
        session_id = session_id or session.get("id")
    item_type = str(body.get("type", ""))
    if item_type == "response.output_text.delta":
        print(body.get("delta", ""), end="", flush=True)
    elif "tool" in item_type or "web_search" in item_type or "mcp" in item_type:
        print(f"[tool] {json.dumps(body, separators=(",", ":"))}", flush=True)
    elif item_type in {"error", "response.failed"} or event_name in {"error", "response.failed"}:
        failed = True
        error = body.get("error") or body.get("response", {}).get("error") or body
        print(f"[error] {json.dumps(error, separators=(",", ":"))}", file=sys.stderr, flush=True)
    elif item_type in {"response.completed", "response.created"}:
        print(f"[state] {item_type}", flush=True)

print()
if session_id:
    print(f"session_id={session_id}")
if failed:
    raise SystemExit(1)
'
