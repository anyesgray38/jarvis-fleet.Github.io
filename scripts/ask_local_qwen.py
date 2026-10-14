#!/usr/bin/env python3
"""Talk to the isolated local Qwen server without changing AEGIS defaults."""
import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="A short question; this model has a 2048-token context")
    parser.add_argument("--max-tokens", type=int, default=192)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 256:
        parser.error("--max-tokens must be between 1 and 256")
    payload = {
        "model": os.getenv("AEGIS_SMALL_QWEN_ALIAS", "aegis-qwen3.5-0.8b-q4_0"),
        "messages": [
            {"role": "system", "content": "You are AEGIS, a local assistant. Answer briefly. Be honest about uncertainty. You cannot execute tools or claim to have performed actions."},
            {"role": "user", "content": args.prompt},
        ],
        "max_tokens": args.max_tokens,
        "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    started = time.monotonic()
    request = Request("http://127.0.0.1:8081/v1/chat/completions",
                      data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=180) as response:
            result = json.load(response)
        answer = result["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Model returned no answer")
        print(answer.strip())
        print(f"\n[Local Qwen 0.8B | {time.monotonic() - started:.1f}s | no hosted inference]", file=sys.stderr)
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError) as exc:
        print(f"Local Qwen failed: {exc}. Start scripts/start_local_qwen.sh first.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
