"""Fail-closed sanitization for browser data crossing into AEGIS.

Browser pages are untrusted data. This boundary validates local CDP targets,
limits the governed YouTube navigation surface, and returns bounded metadata so
page text cannot become an instruction or pollute build artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
import html
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from typing import Any, Iterable


class BrowserSanitizationError(ValueError):
    """Raised when browser input crosses an unsafe boundary."""


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE = re.compile(r"\s+")


def sanitize_browser_text(value: Any, *, maximum: int = 240) -> str:
    """Normalize untrusted page text and enforce a strict size bound."""
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", html.unescape(value))
    normalized = _CONTROL_CHARS.sub("", normalized)
    normalized = _SPACE.sub(" ", normalized).strip()
    return normalized[:maximum]


def sanitize_cdp_url(value: str) -> str:
    """Allow only loopback HTTP(S) CDP endpoints without credentials."""
    if not isinstance(value, str) or not value.strip():
        raise BrowserSanitizationError("CDP URL is required")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BrowserSanitizationError("CDP URL must use http(s) and include a host")
    if parsed.hostname.casefold() not in _LOOPBACK_HOSTS:
        raise BrowserSanitizationError("CDP URL must point to loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BrowserSanitizationError("CDP URL cannot contain credentials, query, or fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise BrowserSanitizationError("CDP URL has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise BrowserSanitizationError("CDP URL port is outside the valid range")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")).rstrip("/")


def sanitize_youtube_navigation_url(value: str) -> str:
    """Allow only canonical YouTube results and watch URLs."""
    if not isinstance(value, str) or not value.strip():
        raise BrowserSanitizationError("browser navigation URL is required")
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in _YOUTUBE_HOSTS:
        raise BrowserSanitizationError("governed browser navigation is limited to YouTube HTTPS URLs")
    query = parse_qs(parsed.query, keep_blank_values=False)
    if parsed.path == "/results":
        search = sanitize_browser_text(query.get("search_query", [""])[0], maximum=160)
        if not search:
            raise BrowserSanitizationError("YouTube results URL requires a search query")
        return "https://www.youtube.com/results?" + urlencode({"search_query": search})
    if parsed.path == "/watch":
        video_id = query.get("v", [""])[0]
        if not _VIDEO_ID.fullmatch(video_id):
            raise BrowserSanitizationError("YouTube watch URL has an invalid video id")
        return "https://www.youtube.com/watch?" + urlencode({"v": video_id})
    raise BrowserSanitizationError("governed browser navigation is limited to YouTube results and watch pages")


def sanitize_youtube_results(rows: Iterable[Any], *, limit: int = 20) -> list[dict[str, str]]:
    """Keep only bounded, canonical YouTube result metadata."""
    if limit < 1:
        return []
    clean: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        title = sanitize_browser_text(row.get("title"), maximum=240)
        try:
            href = sanitize_youtube_navigation_url(str(row.get("href", "")))
        except BrowserSanitizationError:
            continue
        if "/watch?" not in href or not title or href in seen:
            continue
        seen.add(href)
        clean.append({"title": title, "href": href})
        if len(clean) >= limit:
            break
    return clean


@dataclass(frozen=True)
class BrowserRuntimePaths:
    """Filesystem locations for browser state, kept outside the source tree."""

    root: Path

    @classmethod
    def from_environment(cls) -> "BrowserRuntimePaths":
        configured = os.environ.get("AEGIS_BROWSER_RUNTIME_DIR", "")
        root = Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "aegis-browser"
        return cls(root.resolve())

    def assert_outside(self, workspace: str | Path) -> Path:
        workspace_path = Path(workspace).expanduser().resolve()
        if self.root == workspace_path or workspace_path in self.root.parents:
            raise BrowserSanitizationError("browser runtime directory must be outside the workspace")
        return self.root
