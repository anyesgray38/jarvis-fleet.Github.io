"""Read-only Chrome connectivity diagnostics for AEGIS.

The diagnostician observes local browser availability and the configured Chrome
DevTools endpoint. It never starts a browser, changes browser state, or
installs software; remediation is returned as an operator-facing suggestion.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_CDP_URL = os.environ.get("AEGIS_CHROME_CDP_URL", "http://127.0.0.1:9222").rstrip("/")
KNOWN_BROWSER_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def _browser_executable(binary: str = "") -> str | None:
    candidates = (binary,) if binary else KNOWN_BROWSER_NAMES
    for candidate in candidates:
        if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
            return str(Path(candidate).resolve()) if Path(candidate).is_file() else str(shutil.which(candidate))
    return None


def _running_browser_count() -> int:
    """Count browser processes without exposing command-line arguments."""
    proc = Path("/proc")
    if not proc.is_dir():
        return 0
    count = 0
    names = set(KNOWN_BROWSER_NAMES)
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        # argv[0] identifies the process executable. Looking at every argument
        # would falsely classify `jarvis diagnose chrome` as a Chrome process.
        executable = fields[0].decode("utf-8", "ignore") if fields else ""
        if Path(executable).name in names:
            count += 1
    return count


def _endpoint(base_url: str, timeout: float = 3.0) -> dict[str, Any]:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"reachable": False, "error": "CDP URL must be an http(s) URL with a host"}

    result: dict[str, Any] = {"reachable": False, "url": base_url}
    try:
        request = Request(base_url.rstrip("/") + "/json/version", headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            version = json.loads(response.read(2_000_000).decode("utf-8"))
        request = Request(base_url.rstrip("/") + "/json/list", headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            targets = json.loads(response.read(2_000_000).decode("utf-8"))
        pages = [item for item in targets if isinstance(item, dict) and item.get("type") == "page"] if isinstance(targets, list) else []
        result.update({
            "reachable": True,
            "browser": str(version.get("Browser", "")) if isinstance(version, dict) else "",
            "pages": len(pages),
            "attachable_pages": sum(1 for item in pages if item.get("webSocketDebuggerUrl")),
        })
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
    return result


class ChromeDiagnosticsAgent:
    """Specialist agent that explains why AEGIS cannot attach to Chrome."""

    name = "chrome_diagnostician"

    def __init__(
        self,
        *,
        endpoint_probe: Callable[[str, float], dict[str, Any]] = _endpoint,
        executable_finder: Callable[[str], str | None] = _browser_executable,
        process_counter: Callable[[], int] = _running_browser_count,
    ) -> None:
        self.endpoint_probe = endpoint_probe
        self.executable_finder = executable_finder
        self.process_counter = process_counter

    def diagnose(self, *, cdp_url: str = DEFAULT_CDP_URL, browser_binary: str = "", timeout: float = 3.0) -> dict[str, Any]:
        endpoint = self.endpoint_probe(cdp_url.rstrip("/"), timeout)
        executable = self.executable_finder(browser_binary)
        processes = self.process_counter()
        attachable = int(endpoint.get("attachable_pages", 0) or 0)

        if endpoint.get("reachable") and attachable:
            status = "ready"
            diagnosis = "Chrome DevTools is reachable and an attachable page is available."
            recommendations: list[str] = []
        elif endpoint.get("reachable"):
            status = "degraded"
            diagnosis = "Chrome DevTools is reachable, but no attachable page is available."
            recommendations = ["Open a normal Chrome tab and rerun the diagnostic."]
        elif not executable and not processes:
            status = "blocked"
            diagnosis = "No Chrome/Chromium executable or running browser process was detected."
            recommendations = ["Install Chrome or Chromium, then start it with remote debugging enabled."]
        elif executable and not processes:
            status = "blocked"
            diagnosis = "A browser executable is installed, but no browser process is running."
            recommendations = [f"Start the browser with: {executable} --remote-debugging-port=9222"]
        elif processes and not endpoint.get("reachable"):
            status = "blocked"
            diagnosis = "A browser process is running, but its DevTools endpoint is not reachable."
            recommendations = [
                "Restart or launch the browser with --remote-debugging-port=9222.",
                "If it is already using another port, set AEGIS_CHROME_CDP_URL to that endpoint.",
            ]
        else:
            status = "blocked"
            diagnosis = "Chrome DevTools is not reachable from this AEGIS process."
            recommendations = ["Verify the browser binary, process, port, and local firewall settings."]

        return {
            "ok": True,
            "agent": self.name,
            "status": status,
            "diagnosis": diagnosis,
            "cdp": endpoint,
            "browser": {"executable": executable, "running_processes": processes},
            "recommendations": recommendations,
            "read_only": True,
        }


def diagnose_chrome(**kwargs: Any) -> dict[str, Any]:
    """Convenience entry point used by the CLI and integrations."""
    return ChromeDiagnosticsAgent().diagnose(**kwargs)
