from __future__ import annotations

import os
from typing import Any

import httpx

from .base import LLMProvider


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.base_url = "https://api.groq.com/openai/v1"

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = self.normalize_model(model)
        payload = {"model": model, "messages": messages, "stream": stream, **kwargs}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> bool:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/models", headers=headers)
                return resp.status_code == 200
        except Exception:
            return False
