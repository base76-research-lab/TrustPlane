from __future__ import annotations

from typing import Any

from .base import LLMProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .groq import GroqProvider
from .cerebras import CerebrasProvider

_REGISTRY: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "groq": GroqProvider,
    "cerebras": CerebrasProvider,
}


def get_provider(name: str, **kwargs: Any) -> LLMProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {name!r}. Available: {list(_REGISTRY)}")
    return cls(**kwargs)
