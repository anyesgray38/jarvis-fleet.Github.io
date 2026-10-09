"""Small OpenAI Files API client for cloud-only research archives."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class OpenAICloudArchive:
    """Upload public research source text without retaining the raw body locally."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.project_id = os.environ.get("OPENAI_PROJECT_ID", "").strip()
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.max_bytes = max(1, int(os.environ.get("AEGIS_KNOWLEDGE_CLOUD_MAX_BYTES", str(50 * 1024 * 1024))))
        requested = _enabled(os.environ.get("AEGIS_KNOWLEDGE_CLOUD_ARCHIVE", "0"))
        self.enabled = bool(self.api_key) and (requested if enabled is None else enabled)

    @staticmethod
    def _multipart(filename: str, content: bytes) -> tuple[bytes, str]:
        boundary = "----aegis-openai-" + secrets.token_hex(16)
        marker = boundary.encode("ascii")
        safe_name = Path(filename).name.replace('"', "_")
        body = b"".join(
            (
                b"--" + marker + b"\r\n",
                b'Content-Disposition: form-data; name="purpose"\r\n\r\n',
                b"user_data\r\n",
                b"--" + marker + b"\r\n",
                f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'.encode("utf-8"),
                b"Content-Type: text/markdown\r\n\r\n",
                content,
                b"\r\n--" + marker + b"--\r\n",
            )
        )
        return body, boundary

    def upload_text(self, filename: str, content: str) -> dict[str, object]:
        if not self.enabled:
            raise RuntimeError("OpenAI cloud archive is disabled")
        encoded = content.encode("utf-8")
        if not encoded.strip():
            raise ValueError("cannot upload empty source content")
        if len(encoded) > self.max_bytes:
            raise ValueError(f"source exceeds cloud archive limit of {self.max_bytes} bytes")
        body, boundary = self._multipart(filename, encoded)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        if self.project_id:
            headers["OpenAI-Project"] = self.project_id
        request = Request(f"{self.base_url}/files", data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
        except HTTPError as error:
            try:
                response = json.loads(error.read(8_000).decode("utf-8"))
                detail = response.get("error", response).get("message", "request rejected")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                detail = "request rejected"
            raise RuntimeError(f"OpenAI Files upload failed: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"OpenAI Files upload failed: {error.reason}") from error
        file_id = payload.get("id")
        if not isinstance(file_id, str) or not file_id:
            raise RuntimeError("OpenAI Files upload returned no file id")
        return {"id": file_id, "filename": payload.get("filename", filename), "bytes": payload.get("bytes", len(encoded))}
