#!/usr/bin/env python3
"""Natural-language AEGIS operator CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = os.getenv("AEGIS_MODEL_RUNTIME_URL", "http://127.0.0.1:8891").rstrip("/")
ORCHESTRATOR_URL = os.getenv("AEGIS_ORCHESTRATOR_URL", "http://127.0.0.1:8888").rstrip("/")
REGISTRY = ROOT / "capabilities" / "registry.json"


class AegisCLIError(RuntimeError):
    pass


class AegisClient:
    """Dependency-free client for existing AEGIS HTTP surfaces."""

    def __init__(self, model_url: str = MODEL_URL, orchestrator_url: str = ORCHESTRATOR_URL):
        self.model_url = model_url.rstrip("/")
        self.orchestrator_url = orchestrator_url.rstrip("/")

    @staticmethod
    def request(url: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 120) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, data=data, headers=headers, method=method),
                timeout=timeout,
            ) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = {"error": raw}
            raise AegisCLIError(f"HTTP {exc.code}: {detail.get('error', detail)}") from exc
        except urllib.error.URLError as exc:
            raise AegisCLIError(f"AEGIS service unavailable: {exc.reason}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AegisCLIError("AEGIS returned invalid JSON") from exc

    def chat(self, prompt: str, purpose: str = "general", system: str | None = None) -> dict[str, Any]:
        messages = ([{"role": "system", "content": system}] if system else [])
        messages.append({"role": "user", "content": prompt})
        return self.request(
            f"{self.model_url}/chat",
            "POST",
            {
                "messages": messages,
                "purpose": purpose,
                "local_only": True,
                "allow_external": False,
                "temperature": 0,
                "max_tokens": 2048,
            },
        )

    def health(self) -> dict[str, Any]:
        return {
            "model_runtime": self.request(f"{self.model_url}/health"),
            "orchestrator": self.request(f"{self.orchestrator_url}/health"),
        }

    def agents(self) -> dict[str, Any]:
        return self.request(f"{self.orchestrator_url}/agents")

    def jobs(self) -> dict[str, Any]:
        return self.request(f"{self.orchestrator_url}/jobs")

    def job(self, job_id: int) -> dict[str, Any]:
        return self.request(f"{self.orchestrator_url}/jobs/{job_id}")

    def shell(self, agent_id: int, command: str) -> dict[str, Any]:
        return self.request(f"{self.orchestrator_url}/agents/{agent_id}/shell", "POST", {"cmd": command})

    def broadcast(self, command: str, tags: list[str]) -> dict[str, Any]:
        return self.request(f"{self.orchestrator_url}/broadcast", "POST", {"cmd": command, "tags": tags})

    def queue(self, hostname: str, command: str) -> dict[str, Any]:
        return self.request(f"{self.orchestrator_url}/queue", "POST", {"hostname": hostname, "cmd": command})


def load_capabilities() -> list[dict[str, Any]]:
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AegisCLIError(f"cannot load capability registry: {exc}") from exc
    return sorted(data.get("capabilities", []), key=lambda item: item.get("id", ""))


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


PLANNER_SYSTEM = """You are the AEGIS planning assistant.
Convert the operator's natural-language request into a safe, explicit implementation plan.
You are planning, not executing. Never invent capabilities.
Prefer inspect -> change -> test -> verify.
Return JSON only:
{
  "objective": "string",
  "steps": [
    {
      "id": "stable-step-id",
      "capability": "registered.capability.id",
      "input": {},
      "depends_on": [],
      "verification": {"required": true},
      "constraints": {}
    }
  ],
  "notes": []
}
If information is missing, put the question in notes rather than guessing.
"""


def make_plan(client: AegisClient, objective: str) -> dict[str, Any]:
    catalog = json.dumps(load_capabilities(), ensure_ascii=False, separators=(",", ":"))
    result = client.chat(
        f"Operator request:\n{objective}\n\nRegistered capabilities:\n{catalog}",
        purpose="planning",
        system=PLANNER_SYSTEM,
    )
    content = result.get("response", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise AegisCLIError("planner returned no content")
    content = content.strip()
    if content.startswith("FENCE"):
        content = content.replace("FENCEjson", "", 1).replace("FENCE", "").strip()
    try:
        plan = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AegisCLIError("planner did not return valid JSON") from exc
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        raise AegisCLIError("planner returned an invalid plan")
    known = {item["id"] for item in load_capabilities()}
    for step in plan["steps"]:
        if not isinstance(step, dict) or step.get("capability") not in known:
            raise AegisCLIError(f"unregistered capability selected: {step.get('capability')}")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aegis", description="Natural-language AEGIS operator CLI")
    parser.add_argument("--model-url", default=MODEL_URL)
    parser.add_argument("--orchestrator-url", default=ORCHESTRATOR_URL)
    sub = parser.add_subparsers(dest="command")

    for name in ("health", "agents", "jobs", "capabilities"):
        sub.add_parser(name)

    chat = sub.add_parser("chat")
    chat.add_argument("prompt")

    for name in ("plan", "run"):
        cmd = sub.add_parser(name)
        cmd.add_argument("objective")

    job = sub.add_parser("job")
    job.add_argument("id", type=int)

    shell = sub.add_parser("shell")
    shell.add_argument("agent_id", type=int)
    shell.add_argument("command")

    broadcast = sub.add_parser("broadcast")
    broadcast.add_argument("command")
    broadcast.add_argument("--tag", action="append", default=[])

    queue = sub.add_parser("queue")
    queue.add_argument("hostname")
    queue.add_argument("command")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    client = AegisClient(args.model_url, args.orchestrator_url)
    try:
        if args.command == "health":
            print_json(client.health())
        elif args.command == "agents":
            print_json(client.agents())
        elif args.command == "jobs":
            print_json(client.jobs())
        elif args.command == "job":
            print_json(client.job(args.id))
        elif args.command == "capabilities":
            print_json(load_capabilities())
        elif args.command == "chat":
            print(client.chat(args.prompt).get("response", {}).get("content", ""))
        elif args.command in ("plan", "run"):
            plan = make_plan(client, args.objective)
            print_json(plan)
            print("\nPlan generated. Execution remains a separate governed step.")
        elif args.command == "shell":
            print_json(client.shell(args.agent_id, args.command))
        elif args.command == "broadcast":
            print_json(client.broadcast(args.command, args.tag))
        elif args.command == "queue":
            print_json(client.queue(args.hostname, args.command))
    except AegisCLIError as exc:
        print(f"AEGIS: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
