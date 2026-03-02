from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for all LLM provider adapters."""

    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a chat completion request and return OpenAI-compatible response."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check if the provider is reachable."""
        ...

    def normalize_model(self, model: str) -> str:
        """Strip provider prefix if present, e.g. 'ollama/llama3.2' -> 'llama3.2'."""
        if "/" in model:
            _, model = model.split("/", 1)
        return model
