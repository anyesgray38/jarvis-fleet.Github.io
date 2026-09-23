"""OpenAI API provider for AEGIS.

Uses the shared OpenAI-compatible transport while keeping the OpenAI
credential in the runtime environment rather than source control.
"""

from __future__ import annotations

import os

from .openai_compatible import OpenAICompatibleConfig, OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """Hosted OpenAI provider authenticated with OPENAI_API_KEY."""

    provider_id = "openai"

    def __init__(
        self,
        *,
        base_url: str = "https://api.openai.com",
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        super().__init__(
            provider_id=self.provider_id,
            config=OpenAICompatibleConfig(
                base_url=base_url,
                api_key=key,
                timeout=timeout,
            ),
        )
