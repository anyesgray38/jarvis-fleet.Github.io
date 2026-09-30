#!/usr/bin/env python3
"""Materialize the declared Linux execution profile into a clean directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "deploy" / "linux-computer-control.json"


def load_profile() -> dict:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if profile.get("profile") != "linux-computer-control":
        raise ValueError("unexpected Linux profile")
    return profile


def export_profile(output: Path) -> list[str]:
    profile = load_profile()
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("output must be outside the source repository")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for relative in profile["included_paths"]:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(relative)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative)

    registry_relative = "capabilities/registry.json"
    registry = json.loads((output / registry_relative).read_text(encoding="utf-8"))
    allowed = set(profile["capabilities"])
    registry["capabilities"] = [
        item for item in registry.get("capabilities", [])
        if isinstance(item, dict) and item.get("id") in allowed
    ]
    (output / registry_relative).write_text(
        json.dumps(registry, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (output / "PROFILE.json").write_text(
        json.dumps(profile, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    copied = export_profile(args.output)
    print(json.dumps({"ok": True, "output": str(args.output.resolve()), "files": len(copied)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
