"""Linux-friendly command line interface for Jarvis safety controls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from security.safety import SafetySettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis", description="Jarvis control-plane CLI")
    sub = parser.add_subparsers(dest="command")

    safety = sub.add_parser("safety", help="view and change runtime safety controls")
    safety_sub = safety.add_subparsers(dest="safety_command")

    safety_sub.add_parser("list", help="show all safety controls")
    enable = safety_sub.add_parser("enable", help="enable a safety control")
    enable.add_argument("control")
    disable = safety_sub.add_parser("disable", help="disable a safety control")
    disable.add_argument("control")

    show = safety_sub.add_parser("show", help="show one safety control")
    show.add_argument("control")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = SafetySettings()

    if args.command != "safety":
        parser.print_help()
        return 0

    if args.safety_command in {None, "list"}:
        for key, value in settings.snapshot().items():
            print(f"{key}: {'ON' if value else 'OFF'}")
        return 0

    if args.safety_command == "show":
        try:
            value = settings.enabled(args.control)
        except KeyError as exc:
            print(str(exc))
            return 2
        print(f"{args.control}: {'ON' if value else 'OFF'}")
        return 0

    if args.safety_command in {"enable", "disable"}:
        enabled = args.safety_command == "enable"
        try:
            settings.set(args.control, enabled)
        except KeyError as exc:
            print(str(exc))
            return 2
        print(f"{args.control}: {'ON' if enabled else 'OFF'}")
        print(f"saved to {Path(settings.path)}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
