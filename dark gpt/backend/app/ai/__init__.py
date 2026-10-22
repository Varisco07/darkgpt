"""Motore AI: provider, prompt e integrazione tool-calling."""

from .provider import LlmResponse, LLMProvider, MockProvider, OpenAICompatProvider, get_provider
from .prompts import get_prompt

__all__ = [
    "LLMProvider",
    "LlmResponse",
    "MockProvider",
    "OpenAICompatProvider",
    "get_prompt",
    "get_provider",
]
