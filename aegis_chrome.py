#!/usr/bin/env python3
"""Dependency-free Chrome DevTools control for the AEGIS terminal CLI.

This is intentionally separate from Hermes.  It attaches to an operator-owned
Chrome instance through its local DevTools HTTP/WebSocket endpoint, performs a
bounded YouTube workflow, and verifies that an approximately one-hour video is
actively playing.  It never accepts arbitrary JavaScript from the CLI.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import socket
import struct
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

from security.safety import SafetyController, SafetySettings


DEFAULT_CDP_URL = os.environ.get("AEGIS_CHROME_CDP_URL", "http://127.0.0.1:9222").rstrip("/")
MIN_DEFAULT_SECONDS = 45 * 60
MAX_DEFAULT_SECONDS = 90 * 60


class ChromeControlError(RuntimeError):
    pass


def _http_json(base_url: str, path: str) -> Any:
    try:
        request = Request(base_url.rstrip("/") + path, headers={"Accept": "application/json"})
        with urlopen(request, timeout=4) as response:
            return json.loads(response.read(2_000_000).decode("utf-8"))
    except Exception as exc:
        raise ChromeControlError(
            f"Chrome DevTools endpoint unavailable at {base_url}; start Chrome with remote debugging "
            f"or set AEGIS_CHROME_CDP_URL. Detail: {exc}"
        ) from exc


class _WebSocket:
    """Minimal RFC 6455 client for the Chrome DevTools Protocol."""

    def __init__(self, ws_url: str, timeout: float = 15.0):
        parsed = urlsplit(ws_url)
        if parsed.scheme != "ws" or not parsed.hostname:
            raise ChromeControlError("Chrome returned an invalid WebSocket debugger URL")
        self.sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port or 80}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.sock.sendall(request)
        response = self._read_until(b"\r\n\r\n", 16_384)
        if not response.startswith(b"HTTP/1.1 101"):
            self.close()
            raise ChromeControlError("Chrome rejected the DevTools WebSocket handshake")
        self._next_id = 1

    def _read_until(self, marker: bytes, maximum: int) -> bytes:
        data = bytearray()
        while marker not in data and len(data) < maximum:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    def _read_exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ChromeControlError("Chrome DevTools WebSocket closed unexpectedly")
            data.extend(chunk)
        return bytes(data)

    def _send(self, payload: str, opcode: int = 1) -> None:
        raw = payload.encode("utf-8")
        mask = os.urandom(4)
        if len(raw) < 126:
            header = bytes([0x80 | opcode, 0x80 | len(raw)])
        elif len(raw) <= 0xFFFF:
            header = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack("!H", len(raw))
        else:
            header = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack("!Q", len(raw))
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(raw))
        self.sock.sendall(header + mask + masked)

    def _receive(self) -> tuple[int, bytes]:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        masked = bool(second & 0x80)
        mask = self._read_exact(4) if masked else b""
        data = self._read_exact(length)
        if masked:
            data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        return opcode, data

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        fragments: list[bytes] = []
        while True:
            opcode, data = self._receive()
            if opcode == 0x9:
                self._send(data.decode("utf-8", "ignore"), opcode=0xA)
                continue
            if opcode == 0x8:
                raise ChromeControlError("Chrome DevTools WebSocket closed")
            if opcode in {0x1, 0x0}:
                fragments.append(data)
                if opcode == 0x1 or fragments:
                    try:
                        message = json.loads(b"".join(fragments).decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    fragments.clear()
                    if message.get("id") != request_id:
                        continue
                    if "error" in message:
                        raise ChromeControlError(str(message["error"]))
                    return message.get("result", {})

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class ChromeSession:
    def __init__(self, cdp_url: str = DEFAULT_CDP_URL, target: str = ""):
        self.cdp_url = cdp_url.rstrip("/")
        raw_targets = _http_json(self.cdp_url, "/json/list")
        targets = [
            item for item in raw_targets
            if isinstance(item, dict) and item.get("type") == "page" and item.get("webSocketDebuggerUrl")
        ]
        if target:
            wanted = target.casefold()
            targets = [item for item in targets if wanted in f"{item.get('title', '')} {item.get('url', '')}".casefold()]
        if not targets:
            raise ChromeControlError("No attachable Chrome page was found at the DevTools endpoint")
        self.target = targets[0]
        self.ws = _WebSocket(str(self.target["webSocketDebuggerUrl"]))
        self.ws.call("Page.enable")
        self.ws.call("Runtime.enable")

    def evaluate(self, expression: str, *, await_promise: bool = True) -> Any:
        result = self.ws.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True,
            "userGesture": True,
        })
        exception = result.get("exceptionDetails")
        if exception:
            raise ChromeControlError(str(exception.get("text", "Chrome evaluation failed")))
        value = result.get("result", {}).get("value")
        return value

    def navigate(self, url: str) -> None:
        self.ws.call("Page.navigate", {"url": url})

    def wait_for(self, expression: str, timeout: float = 20.0) -> Any:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.evaluate(expression)
            if value:
                return value
            time.sleep(0.5)
        return None

    def close(self) -> None:
        self.ws.close()


def _dismiss_consent(session: ChromeSession) -> None:
    session.evaluate(r"""(() => {
      const labels = ['Accept all', 'I agree', 'Accept', 'Got it'];
      const nodes = [...document.querySelectorAll('button, tp-yt-paper-button, [role="button"]')];
      const hit = nodes.find(node => labels.includes((node.innerText || node.getAttribute('aria-label') || '').trim()));
      if (hit) { hit.click(); return true; }
      return false;
    })()""")


def _results(session: ChromeSession) -> list[dict[str, str]]:
    value = session.wait_for(r"""(() => {
      const rows = [...document.querySelectorAll('a#video-title')]
        .map(a => ({title: (a.textContent || '').trim(), href: a.href}))
        .filter(x => x.title && x.href && x.href.includes('watch?v='));
      return rows.length ? rows.slice(0, 20) : null;
    })()""", 25)
    return value if isinstance(value, list) else []


def _play_video(session: ChromeSession) -> dict[str, Any] | None:
    session.wait_for("!!document.querySelector('video')", 30)
    session.evaluate(r"""(() => {
      const video = document.querySelector('video');
      const button = document.querySelector('.ytp-play-button');
      if (button && button.getAttribute('aria-label')?.toLowerCase().includes('play')) button.click();
      if (video) { video.muted = false; video.volume = 0.35; return video.play().then(() => true).catch(() => false); }
      return false;
    })()""")
    return session.wait_for(r"""(() => {
      const v = document.querySelector('video');
      return v && !v.paused && v.currentTime > 0 ? {duration: v.duration, currentTime: v.currentTime, muted: v.muted} : null;
    })()""", 20)


def play_bedtime_music(
    *,
    cdp_url: str = DEFAULT_CDP_URL,
    target: str = "",
    query: str = "one hour bedtime music",
    min_seconds: int = MIN_DEFAULT_SECONDS,
    max_seconds: int = MAX_DEFAULT_SECONDS,
    safety: SafetySettings | None = None,
) -> dict[str, Any]:
    SafetyController(safety or SafetySettings()).require("desktop_control")
    if min_seconds < 60 or max_seconds <= min_seconds:
        raise ValueError("duration bounds are invalid")
    session = ChromeSession(cdp_url, target)
    try:
        search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
        session.navigate(search_url)
        session.wait_for("document.readyState === 'complete'", 20)
        _dismiss_consent(session)
        candidates = _results(session)
        if not candidates:
            raise ChromeControlError("YouTube results did not load in the connected Chrome page")
        checked: list[dict[str, Any]] = []
        for candidate in candidates[:8]:
            session.navigate(candidate["href"])
            session.wait_for("document.readyState === 'complete'", 20)
            state = _play_video(session)
            duration = float(state.get("duration", 0)) if isinstance(state, dict) else 0.0
            checked.append({"title": candidate["title"], "duration_seconds": duration})
            if state and min_seconds <= duration <= max_seconds:
                return {
                    "ok": True,
                    "playing": True,
                    "title": candidate["title"],
                    "url": candidate["href"],
                    "duration_seconds": duration,
                    "duration_minutes": round(duration / 60, 1),
                    "target": self_target(session),
                    "checked": checked,
                }
        raise ChromeControlError(f"No result in the first {len(checked)} candidates matched the requested duration")
    finally:
        session.close()


def self_target(session: ChromeSession) -> dict[str, str]:
    return {"title": str(session.target.get("title", "")), "url": str(session.target.get("url", ""))}
