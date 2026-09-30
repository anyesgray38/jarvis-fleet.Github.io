#!/usr/bin/env python3
"""Bounded local desktop-control runtime for AEGIS.

The model never receives direct OS APIs.  It talks to this loopback-only
service, which performs observation, policy checks, input delivery, bounded
verification, recovery-safe error handling, and audit logging.  The preferred
backend is the installed cua-driver MCP process; the service remains useful in
degraded mode when capture or accessibility is unavailable.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import select
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
from typing import Any, Protocol

from security.safety import SafetyController, SafetySettings


ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = int(os.environ.get("AEGIS_DESKTOP_PORT", "8894"))
MAX_BODY_BYTES = 1_000_000
MAX_TYPE_CHARS = 2_000
MAX_AUDIT_BYTES = 10_000_000
SENSITIVE_MARKERS = {"password", "passwd", "secret", "token", "pin", "otp"}
X11_WINDOW_LINE = re.compile(
    r'^\s+(0x[0-9a-fA-F]+)\s+"(.*?)":.*?'
    r'(\d+)x(\d+)[+-]\d+[+-]\d+\s+([+-]\d+)([+-]\d+)\s*$'
)
X11_PID_LINE = re.compile(r'_NET_WM_PID\(CARDINAL\)\s*=\s*(\d+)')
CONFIRMATION_CLASSES = {
    "sudo": "desktop_sudo_prompts",
    "payment": "desktop_payments",
    "file_deletion": "desktop_file_deletion",
    "security_change": "desktop_security_changes",
}


class Backend(Protocol):
    name: str

    def status(self) -> dict[str, Any]: ...
    def observe(self) -> dict[str, Any]: ...
    def screenshot(self) -> dict[str, Any]: ...
    def action(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def close(self) -> None: ...

    def cursor(self) -> dict[str, Any]: ...


class UnavailableBackend:
    name = "unavailable"

    def __init__(self, reason: str):
        self.reason = reason

    def status(self) -> dict[str, Any]:
        return {"name": self.name, "available": False, "reason": self.reason}

    def observe(self) -> dict[str, Any]:
        return {"ok": False, "error": self.reason, "backend": self.name}

    def screenshot(self) -> dict[str, Any]:
        return {"ok": False, "error": self.reason, "backend": self.name}

    def action(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": self.reason, "backend": self.name, "action": action}

    def close(self) -> None:
        return None

    def cursor(self) -> dict[str, Any]:
        return {}


class CuaDriverBackend:
    """Small persistent JSON-RPC client for ``cua-driver mcp``."""

    name = "cua-driver"

    def __init__(
        self,
        binary: str | None = None,
        *,
        timeout: float = 15.0,
        driver_env: dict[str, str | None] | None = None,
    ):
        candidate = binary or os.environ.get("AEGIS_CUA_DRIVER") or shutil.which("cua-driver")
        if not candidate:
            managed_candidate = Path.home() / ".local/bin/cua-driver"
            package_candidate = Path.home() / ".cua-driver/packages/current/cua-driver"
            hermes_candidate = Path.home() / ".hermes/tools/cua-driver-0.21.0-linux-x64/cua-driver"
            if managed_candidate.exists():
                candidate = str(managed_candidate)
            elif package_candidate.exists():
                candidate = str(package_candidate)
            elif hermes_candidate.exists():
                candidate = str(hermes_candidate)
        self.binary = candidate
        self.timeout = max(2.0, min(60.0, float(timeout)))
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._next_id = 1
        self._driver_env = dict(driver_env or {})
        self._x11_backend: CuaDriverBackend | None = None
        self._screen_size: dict[str, Any] = {}
        self._accessibility_timeout_ms = max(
            100,
            min(120_000, int(os.environ.get("AEGIS_CUA_A11Y_TIMEOUT_MS", "3000"))),
        )

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": bool(self.binary and Path(self.binary).exists()),
            "binary": self.binary,
            "session": bool(self._proc and self._proc.poll() is None),
            "screen_size": self._screen_size or None,
        }

    def _ensure(self) -> None:
        if not self.binary or not Path(self.binary).exists():
            raise RuntimeError("cua-driver is not installed")
        if self._proc and self._proc.poll() is None:
            return
        self.close()
        child_env = dict(os.environ)
        for key, value in self._driver_env.items():
            if value is None:
                child_env.pop(key, None)
            else:
                child_env[key] = value
        self._proc = subprocess.Popen(
            [self.binary, "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            close_fds=True,
            env=child_env,
        )
        self._rpc("initialize", {})

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            raise RuntimeError("cua-driver session is not active")
        request_id = self._next_id
        self._next_id += 1
        self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
        self._proc.stdin.flush()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                ready, _, _ = select.select([self._proc.stdout], [], [], remaining)
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"cua-driver output wait failed: {exc}") from exc
            if not ready:
                raise TimeoutError(f"cua-driver timed out on {method}")
            line = self._proc.stdout.readline()
            if not line:
                error = "cua-driver exited"
                if self._proc.stderr:
                    try:
                        error = self._proc.stderr.read(500).strip() or error
                    except OSError:
                        pass
                raise RuntimeError(error[:500])
            response = json.loads(line)
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise RuntimeError(str(response["error"])[:500])
            result = response.get("result")
            return result if isinstance(result, dict) else {"value": result}
        raise TimeoutError(f"cua-driver timed out on {method}")

    @staticmethod
    def _structured(result: dict[str, Any]) -> dict[str, Any]:
        value = result.get("structuredContent")
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _error_text(result: dict[str, Any]) -> str:
        chunks = []
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("text"):
                chunks.append(str(item["text"]))
        return " ".join(chunks)[:500] or "cua-driver returned an error"

    def _call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._ensure()
            result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
            if result.get("isError") is True:
                raise RuntimeError(self._error_text(result))
            return result

    @staticmethod
    def _is_stale_window_error(error: BaseException) -> bool:
        text = str(error).casefold()
        return "stale" in text and ("window" in text or "target" in text)

    def _call_window_state(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Retry one window-state request after refreshing a stale CUA session.

        The XWayland window list is obtained independently through X11.  A
        long-lived CUA MCP process can retain an older target registry after a
        browser is launched or relaunched, even though the same exact target
        works in a fresh CUA process.  Reopening only on the driver's explicit
        stale-target error keeps normal requests persistent while recovering
        this observable race safely.
        """
        try:
            return self._call("get_window_state", arguments)
        except Exception as exc:
            if not self._is_stale_window_error(exc):
                raise
            self.close()
            return self._call("get_window_state", arguments)

    def _x11_capture_backend(self) -> CuaDriverBackend:
        """Return a helper CUA session with native-Wayland probing disabled.

        The main session must keep native Wayland enabled for discovery and
        AT-SPI actions.  On Sommelier, however, the driver's X11 image path
        is selected only when the child process is started without the native
        Wayland feature flag.  Keep that compatibility choice isolated to a
        lazily-created capture session.
        """
        with self._lock:
            if self._x11_backend is None:
                self._x11_backend = CuaDriverBackend(
                    self.binary,
                    timeout=self.timeout,
                    driver_env={"CUA_DRIVER_RS_ENABLE_WAYLAND": None},
                )
            return self._x11_backend

    @staticmethod
    def _x11_windows() -> list[dict[str, Any]]:
        """Discover visible X11 windows omitted by the CUA window enumerator.

        ChromeOS/Sommelier can expose a real X11 application window while the
        CUA driver's native enumerator returns only its cursor overlay. This
        bounded fallback uses the display's own window tree and properties,
        then leaves capture and input delivery to the CUA driver.
        """
        if not os.environ.get("DISPLAY") or not shutil.which("xwininfo") or not shutil.which("xprop"):
            return []
        env = dict(os.environ)
        try:
            tree = subprocess.run(
                ["xwininfo", "-root", "-tree"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=2,
                check=False,
            ).stdout[:100_000]
        except (OSError, subprocess.TimeoutExpired):
            return []
        windows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for line in tree.splitlines():
            match = X11_WINDOW_LINE.match(line)
            if not match:
                continue
            window_id = int(match.group(1), 16)
            title = match.group(2).strip()
            width, height = int(match.group(3)), int(match.group(4))
            if window_id in seen or width < 80 or height < 80 or "Cua.AgentCursorOverlay" in title:
                continue
            try:
                props = subprocess.run(
                    ["xprop", "-id", hex(window_id), "_NET_WM_PID", "WM_NAME", "WM_CLASS"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    timeout=1,
                    check=False,
                ).stdout[:4_000]
            except (OSError, subprocess.TimeoutExpired):
                continue
            pid_match = X11_PID_LINE.search(props)
            if not pid_match:
                continue
            pid = int(pid_match.group(1))
            if not Path(f"/proc/{pid}").exists():
                continue
            seen.add(window_id)
            windows.append({
                "app_name": "x11",
                "bounds": {"height": height, "width": width, "x": int(match.group(5)), "y": int(match.group(6))},
                "height": height,
                "is_on_screen": True,
                "pid": pid,
                "title": title,
                "width": width,
                "window_id": window_id,
                "x": int(match.group(5)),
                "y": int(match.group(6)),
                "z_index": 0,
            })
        return windows

    def _windows(self) -> list[dict[str, Any]]:
        # On XWayland/ChromeOS the native enumerator can block while Chromium
        # is publishing accessibility state. The X11 tree is bounded and
        # already gives us the pid/window_id needed for capture and input.
        x11_windows = self._x11_windows()
        if x11_windows:
            return x11_windows
        windows_result = self._call("list_windows")
        windows = self._structured(windows_result).get("windows", [])
        if not isinstance(windows, list):
            windows = []
        usable = [
            item for item in windows
            if isinstance(item, dict)
            and isinstance(item.get("pid"), int)
            and isinstance(item.get("window_id"), int)
        ]
        if usable:
            return windows
        return windows

    def observe(self) -> dict[str, Any]:
        with self._lock:
            size = self._structured(self._call("get_screen_size"))
            self._screen_size = size
            cursor = self._structured(self._call("get_cursor_position"))
            windows = self._windows()
            try:
                tree_result = self._call("get_accessibility_tree")
            except Exception as exc:
                tree_result = {"content": [{"type": "text", "text": str(exc)[:500]}]}
            elements: list[dict[str, Any]] = []
            accessibility_error = "no window with a usable pid/window_id was discovered"
            accessibility_degraded = False
            for window in windows:
                if not isinstance(window, dict) or not isinstance(window.get("pid"), int) or not isinstance(window.get("window_id"), int):
                    continue
                try:
                    state = self._call("get_window_state", {
                        "pid": window["pid"], "window_id": window["window_id"],
                        "include_screenshot": False, "max_elements": 300, "max_depth": 20,
                        "timeout_ms": self._accessibility_timeout_ms,
                    })
                    if state.get("isError") is not True:
                        structured = self._structured(state)
                        elements = structured.get("elements", [])
                        accessibility_degraded = bool(structured.get("degraded"))
                        accessibility_error = str(structured.get("degraded_reason", "")) if accessibility_degraded else ""
                        break
                    accessibility_error = self._error_text(state)
                except Exception as exc:
                    accessibility_error = str(exc)[:500]
            return {
                "ok": True,
                "backend": self.name,
                "screen": size,
                "cursor": cursor,
                "windows": windows,
                "accessibility": {
                    "available": bool(elements),
                    "degraded": accessibility_degraded,
                    "elements": elements[:300],
                    "reason": accessibility_error,
                    "discovery_summary": " ".join(
                        str(i.get("text", "")) for i in tree_result.get("content", []) if isinstance(i, dict)
                    )[:20_000],
                },
            }

    def cursor(self) -> dict[str, Any]:
        return self._structured(self._call("get_cursor_position"))

    def screenshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {"isError": True, "content": [{"type": "text", "text": "no capture attempted"}]}
        structured: dict[str, Any] = {}
        images: list[dict[str, Any]] = []
        capture_scope = "desktop"
        fallback_errors: list[str] = []

        def try_window_capture(candidates: list[dict[str, Any]], backend: CuaDriverBackend) -> None:
            nonlocal result, structured, images, capture_scope
            for window in candidates:
                if not isinstance(window, dict) or not isinstance(window.get("pid"), int) or not isinstance(window.get("window_id"), int):
                    continue
                fallback: dict[str, Any] = {}
                try:
                    fallback = backend._call_window_state({
                        "pid": window["pid"], "window_id": window["window_id"],
                        "include_screenshot": True, "max_elements": 300, "max_depth": 20,
                    })
                    candidate = [i for i in fallback.get("content", []) if isinstance(i, dict) and i.get("type") == "image"]
                    if candidate:
                        result, structured, images, capture_scope = fallback, self._structured(fallback), candidate, "window"
                        return
                    error = self._structured(fallback).get("screenshot_error")
                    if error:
                        fallback_errors.append(json.dumps(error, sort_keys=True))
                except Exception as exc:
                    error = self._structured(fallback).get("screenshot_error") or str(exc)
                    if error:
                        fallback_errors.append(str(error)[:800])

        # Sommelier's full-display X11 grab is unreliable, while a validated
        # XWayland application window remains capturable. Prefer the narrow
        # window path and never label it as a desktop capture.
        x11_windows = self._x11_windows()
        if x11_windows:
            try_window_capture(x11_windows, self._x11_capture_backend())

        if not images:
            try:
                result = self._call("get_desktop_state")
            except Exception as exc:
                result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
            structured = self._structured(result)
            images = [i for i in result.get("content", []) if isinstance(i, dict) and i.get("type") == "image"]

        if not images and not x11_windows:
            try_window_capture(self._windows(), self)
        if not images:
            if fallback_errors:
                raise RuntimeError("window capture unavailable: " + fallback_errors[-1][:800])
            raise RuntimeError(self._error_text(result))
        image = images[0]
        data = str(image.get("data", ""))
        if not data:
            raise RuntimeError("cua-driver returned an empty screenshot")
        raw = base64.b64decode(data, validate=True)
        return {"ok": True, "backend": self.name, "capture_scope": capture_scope, "mime_type": image.get("mimeType", "image/png"),
                "bytes": len(raw), "width": structured.get("width") or structured.get("screenshot_width"),
                "height": structured.get("height") or structured.get("screenshot_height"),
                "image_base64": data}

    @staticmethod
    def _target(arguments: dict[str, Any]) -> dict[str, Any]:
        value = dict(arguments)
        value.setdefault("target", {"kind": "desktop", "display_id": "primary"})
        return value

    def action(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action == "click_element":
            allowed = {
                key: arguments[key]
                for key in (
                    "pid", "window_id", "element_index", "element_token",
                    "snapshot_id", "delivery_mode", "session",
                )
                if key in arguments
            }
            allowed.setdefault("delivery_mode", "background")
            return {"ok": True, "backend": self.name, "action": action,
                    "driver": self._structured(self._call("click", allowed))}
        mapping = {
            "move": "move_cursor", "click": "click", "double_click": "double_click",
            "right_click": "right_click", "scroll": "scroll", "type": "type_text",
            "hotkey": "hotkey", "drag": "drag",
        }
        tool = mapping.get(action)
        if not tool:
            raise ValueError(f"unsupported backend action: {action}")
        return {"ok": True, "backend": self.name, "action": action,
                "driver": self._structured(self._call(tool, self._target(arguments)))}

    def close(self) -> None:
        with self._lock:
            if self._x11_backend is not None:
                self._x11_backend.close()
                self._x11_backend = None
            if self._proc is not None:
                try:
                    if self._proc.stdin:
                        self._proc.stdin.close()
                    self._proc.terminate()
                    self._proc.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        self._proc.kill()
                    except OSError:
                        pass
                self._proc = None


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _validate_action(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if action not in {"move", "click", "click_element", "double_click", "right_click", "scroll", "type", "hotkey", "drag", "wait"}:
        raise ValueError(f"unsupported desktop action: {action}")
    value = dict(arguments)
    if action == "click_element":
        try:
            value["pid"] = int(value.get("pid"))
        except (TypeError, ValueError) as exc:
            raise ValueError("click_element requires a positive pid") from exc
        if value["pid"] <= 0:
            raise ValueError("click_element requires a positive pid")
        if not value.get("element_token") and value.get("element_index") is None:
            raise ValueError("click_element requires element_token or element_index")
        if value.get("element_index") is not None:
            try:
                value["element_index"] = int(value["element_index"])
            except (TypeError, ValueError) as exc:
                raise ValueError("element_index must be an integer") from exc
            if value["element_index"] < 0 and not value.get("element_token"):
                raise ValueError("element_index must be non-negative")
            if not value.get("element_token") and not value.get("snapshot_id"):
                raise ValueError("snapshot_id is required with element_index")
        if value.get("window_id") is not None:
            try:
                value["window_id"] = int(value["window_id"])
            except (TypeError, ValueError) as exc:
                raise ValueError("window_id must be an integer") from exc
        delivery = str(value.get("delivery_mode", "background")).casefold()
        if delivery not in {"background", "foreground"}:
            raise ValueError("delivery_mode must be background or foreground")
        value["delivery_mode"] = delivery
    if action in {"move", "click", "double_click", "right_click"}:
        value["x"], value["y"] = _finite(value.get("x"), "x"), _finite(value.get("y"), "y")
    if action == "scroll":
        direction = str(value.get("direction", "")).lower()
        if direction not in {"up", "down", "left", "right"}:
            raise ValueError("scroll direction must be up, down, left, or right")
        value["amount"] = max(1, min(50, int(value.get("amount", 3))))
    if action == "type":
        text = str(value.get("text", ""))
        if not text or len(text) > MAX_TYPE_CHARS:
            raise ValueError(f"text must be between 1 and {MAX_TYPE_CHARS} characters")
        value["text"] = text
        role = str(value.get("target_role", "")).casefold()
        if value.get("sensitive") or any(marker in role for marker in SENSITIVE_MARKERS):
            value["sensitive"] = True
    if action == "hotkey":
        keys = value.get("keys")
        if not isinstance(keys, list) or not 2 <= len(keys) <= 8 or not all(str(k).strip() for k in keys):
            raise ValueError("hotkey keys must contain 2 to 8 non-empty key names")
        value["keys"] = [str(k).strip() for k in keys]
    if action == "drag":
        for name in ("from_x", "from_y", "to_x", "to_y"):
            value[name] = _finite(value.get(name), name)
        value["duration_ms"] = max(0, min(10_000, int(value.get("duration_ms", 500))))
        value["steps"] = max(1, min(200, int(value.get("steps", 20))))
    if action == "wait":
        value["seconds"] = max(0.0, min(30.0, _finite(value.get("seconds", 1), "seconds")))
    return value


@dataclass
class DesktopController:
    backend: Backend
    safety: SafetySettings
    audit_path: Path
    kill_corner: str = "top-left"
    kill_corner_size: int = 8

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self._stopped = False
        self._stop_reason = ""
        self._last_observation: dict[str, Any] | None = None
        self._last_screenshot_hash: str | None = None
        self._audit_lock = threading.Lock()
        self._watchdog = threading.Thread(target=self._watch_kill_corner, daemon=True, name="aegis-desktop-watchdog")
        self._watchdog.start()

    def _record(self, event: str, **data: Any) -> None:
        record = {"timestamp": time.time(), "event": event, "backend": self.backend.name, **data}
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_lock:
            try:
                if self.audit_path.exists() and self.audit_path.stat().st_size > MAX_AUDIT_BYTES:
                    self.audit_path.replace(self.audit_path.with_suffix(".jsonl.1"))
                with self.audit_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            except OSError:
                pass

    def _watch_kill_corner(self) -> None:
        while True:
            time.sleep(0.25)
            if self._stopped:
                continue
            try:
                if hasattr(self.backend, "cursor"):
                    cursor = self.backend.cursor()
                    screen = self.backend.status().get("screen_size") or {}
                else:
                    observed = self.backend.observe()
                    cursor = observed.get("cursor", {}) if isinstance(observed, dict) else {}
                    screen = observed.get("screen", {}) if isinstance(observed, dict) else {}
                width, height = int(screen.get("width", 0)), int(screen.get("height", 0))
                x, y = int(cursor.get("x", -1)), int(cursor.get("y", -1))
                hit = self.kill_corner == "top-left" and x >= 0 and y >= 0 and x <= self.kill_corner_size and y <= self.kill_corner_size
                if self.kill_corner == "top-right" and width:
                    hit = x >= width - self.kill_corner_size and y <= self.kill_corner_size
                if self.kill_corner == "bottom-left" and height:
                    hit = x <= self.kill_corner_size and y >= height - self.kill_corner_size
                if self.kill_corner == "bottom-right" and width and height:
                    hit = x >= width - self.kill_corner_size and y >= height - self.kill_corner_size
                if hit:
                    self.stop("kill_corner")
            except Exception:
                continue

    def health(self) -> dict[str, Any]:
        return {"ok": True, "service": "aegis-desktop-runtime", "stopped": self._stopped,
                "stop_reason": self._stop_reason or None, "safety": self.safety.snapshot(),
                "backend": self.backend.status(), "kill_corner": self.kill_corner,
                "pid": os.getpid()}

    def observe(self) -> dict[str, Any]:
        try:
            result = self.backend.observe()
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "backend": self.backend.name}
        if isinstance(result, dict):
            with self._lock:
                self._last_observation = result
                result = {**result, "stopped": self._stopped, "safety": self.safety.snapshot()}
        self._record("observe", ok=bool(result.get("ok")), error=result.get("error"))
        return result

    def screenshot(self, include_image: bool = True) -> dict[str, Any]:
        try:
            result = self.backend.screenshot()
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "backend": self.backend.name}
        if result.get("ok") and result.get("image_base64"):
            digest = hashlib.sha256(base64.b64decode(result["image_base64"])).hexdigest()
            result = {**result, "sha256": digest}
            self._last_screenshot_hash = digest
            if not include_image:
                result.pop("image_base64", None)
        self._record("screenshot", ok=bool(result.get("ok")), error=result.get("error"), sha256=result.get("sha256"))
        return result

    def _gate(self, action: str, value: dict[str, Any]) -> None:
        if self._stopped:
            raise PermissionError(f"desktop control stopped: {self._stop_reason or 'operator stop'}")
        if action == "type" and value.get("sensitive"):
            raise PermissionError("password and sensitive fields are permanently blocked")
        sensitive_class = str(value.get("sensitive_class", "")).strip().casefold()
        if sensitive_class in CONFIRMATION_CLASSES:
            control = CONFIRMATION_CLASSES[sensitive_class]
            if value.get("confirm") is not True:
                raise PermissionError(f"{sensitive_class} actions require confirm=true")
            SafetyController(self.safety).require(control)
        SafetyController(self.safety).require("desktop_control")

    def action(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        value = _validate_action(action, arguments)
        self._gate(action, value)
        if action == "wait":
            time.sleep(value["seconds"])
            result = {"ok": True, "action": action, "seconds": value["seconds"]}
        else:
            result = self.backend.action(action, value)
        safe_args = {k: ("<redacted>" if k == "text" else v) for k, v in value.items() if k not in {"image_base64"}}
        if action == "type":
            safe_args = {k: v for k, v in safe_args.items() if k != "text"}
            safe_args["text_length"] = len(value["text"])
        self._record("action", action=action, ok=bool(result.get("ok")), arguments=safe_args, error=result.get("error"))
        return result

    def verify(self, condition: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(condition, dict) or len(condition) != 1:
            raise ValueError("verify requires exactly one bounded condition")
        kind, expected = next(iter(condition.items()))
        observed = self.observe()
        if kind == "backend_available":
            value = bool(self.backend.status().get("available"))
        elif kind == "pointer_at":
            pointer = observed.get("cursor", {})
            tolerance = max(0, min(100, int(expected.get("tolerance", 2)))) if isinstance(expected, dict) else 2
            value = abs(float(pointer.get("x", -1)) - float(expected.get("x", -2))) <= tolerance and abs(float(pointer.get("y", -1)) - float(expected.get("y", -2))) <= tolerance
        elif kind == "active_window_contains":
            needle = str(expected).casefold()
            value = any(needle in str(w.get("title", "")).casefold() for w in observed.get("windows", []) if isinstance(w, dict))
        elif kind in {"accessibility_contains", "accessibility_not_contains"}:
            needle = str(expected).casefold()
            elements = (observed.get("accessibility") or {}).get("elements", [])
            haystack = " ".join(
                " ".join(str(element.get(field, "")) for field in ("label", "value", "description", "role"))
                for element in elements if isinstance(element, dict)
            ).casefold()
            contains = needle in haystack
            value = contains if kind == "accessibility_contains" else not contains
        elif kind == "screenshot_changed":
            prior = self._last_screenshot_hash
            shot = self.screenshot(include_image=False)
            value = bool(shot.get("ok") and prior and shot.get("sha256") != prior)
        else:
            raise ValueError("unsupported verify condition")
        result = {"ok": True, "condition": condition, "satisfied": bool(value), "known": True}
        self._record("verify", condition=condition, satisfied=bool(value))
        return result

    def stop(self, reason: str = "operator") -> dict[str, Any]:
        with self._lock:
            self._stopped, self._stop_reason = True, reason
        self._record("stop", reason=reason)
        return {"ok": True, "stopped": True, "reason": reason}

    def resume(self, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise PermissionError("resume requires confirm=true")
        SafetyController(self.safety).require("desktop_control")
        with self._lock:
            self._stopped, self._stop_reason = False, ""
        self._record("resume")
        return {"ok": True, "stopped": False}


def build_controller() -> DesktopController:
    safety_path = Path(os.environ.get("JARVIS_SAFETY_CONFIG", str(ROOT / ".jarvis" / "safety.json")))
    audit_path = Path(os.environ.get("AEGIS_DESKTOP_AUDIT", str(ROOT / ".jarvis" / "desktop_audit.jsonl")))
    backend: Backend
    candidate = os.environ.get("AEGIS_CUA_DRIVER")
    managed_driver = Path.home() / ".local/bin/cua-driver"
    package_driver = Path.home() / ".cua-driver/packages/current/cua-driver"
    hermes_driver = Path.home() / ".hermes/tools/cua-driver-0.21.0-linux-x64/cua-driver"
    if candidate or shutil.which("cua-driver") or managed_driver.exists() or package_driver.exists() or hermes_driver.exists():
        backend = CuaDriverBackend(candidate)
    else:
        backend = UnavailableBackend("no supported desktop backend found; install cua-driver or configure AEGIS_CUA_DRIVER")
    return DesktopController(backend, SafetySettings(safety_path), audit_path,
                             os.environ.get("AEGIS_DESKTOP_KILL_CORNER", "top-left"),
                             max(1, min(100, int(os.environ.get("AEGIS_DESKTOP_KILL_CORNER_SIZE", "8")))))


class Handler(BaseHTTPRequestHandler):
    controller: DesktopController
    server_version = "aegis-desktop-runtime/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return None

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body is too large")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def do_GET(self) -> None:
        try:
            route = urlsplit(self.path)
            if route.path == "/health": self._send(200, self.controller.health()); return
            if route.path == "/observe": self._send(200, self.controller.observe()); return
            if route.path == "/screenshot":
                include = parse_qs(route.query).get("include_image", ["false"])[0].casefold() == "true"
                self._send(200, self.controller.screenshot(include_image=include)); return
            self._send(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self._send(400, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        try:
            value = self._body()
            if self.path == "/action":
                result = self.controller.action(str(value.get("action", "")), value.get("arguments", value))
            elif self.path == "/verify":
                result = self.controller.verify(value.get("condition", value))
            elif self.path == "/stop":
                result = self.controller.stop(str(value.get("reason", "operator")))
            elif self.path == "/resume":
                result = self.controller.resume(value.get("confirm") is True)
            else:
                self._send(404, {"ok": False, "error": "not found"}); return
            self._send(200, result)
        except PermissionError as exc:
            self._send(403, {"ok": False, "error": str(exc)})
        except (ValueError, TypeError, KeyError) as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send(503, {"ok": False, "error": str(exc)})


def serve(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    controller = build_controller()
    Handler.controller = controller
    server = ThreadingHTTPServer((host, port), Handler)
    def shutdown(_sig: int, _frame: Any) -> None:
        controller.stop("process_signal")
        controller.backend.close()
        # ``BaseServer.shutdown`` must be called from a thread other than the
        # one currently inside ``serve_forever``; signal handlers run there.
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(json.dumps({"service": "aegis-desktop-runtime", "host": host, "port": port, "pid": os.getpid()}), flush=True)
    try:
        server.serve_forever()
    finally:
        controller.backend.close()
        server.server_close()


if __name__ == "__main__":
    serve(os.environ.get("AEGIS_DESKTOP_BIND", "127.0.0.1"), int(os.environ.get("AEGIS_DESKTOP_PORT", str(DEFAULT_PORT))))
