"""Provider LLM: interfaccia astratta e adattatore OpenAI-compatible.

Nessuna dipendenza obbligatoria da un singolo provider: l'adattatore parla
l'API `/v1/chat/completions`, compatibile con provider cloud, LM Studio,
Ollama (via `/v1`), vLLM e gateway interni.

Se nessun endpoint e' configurato, il provider `MockProvider` risponde in
modo esplicitamente dichiarato come simulato: la UI marca la risposta.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..core.config import Settings, get_settings
from ..core.errors import ProviderError
from ..core.logging import get_logger
from ..core.security import redact

logger = get_logger("ai")


@dataclass
class ToolCall:
    """Chiamata a un tool richiesta dal modello."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LlmResponse:
    """Risposta del provider LLM."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    simulated: bool = False
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ],
            "model": self.model,
            "simulated": self.simulated,
            "usage": self.usage,
        }


class LLMProvider(Protocol):
    """Interfaccia minima di un provider LLM."""

    name: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> LlmResponse | Iterator[str]:
        """Esegue una chat. Con `stream=True` restituisce un iteratore di token."""
        ...


class MockProvider:
    """Provider di fallback dichiarato: NON e' un LLM.

    Risponde spiegando che il provider non e' configurato. Le risposte sono
    marcate `simulated=True` e la UI le evidenzia.
    """

    name = "mock"

    def __init__(self, reason: str = "nessun provider LLM configurato") -> None:
        self.reason = reason

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> LlmResponse | Iterator[str]:
        text = (
            "**Provider LLM non configurato.**\n\n"
            f"{self.reason}.\n\n"
            "Per abilitare l'analisi assistita imposta le variabili:\n"
            "- `DARKGPT_LLM_BASE_URL` (es. `http://localhost:11434/v1` per Ollama, "
            "`https://api.openai.com/v1` per OpenAI)\n"
            "- `DARKGPT_LLM_API_KEY` (facoltativa per gli endpoint locali)\n"
            "- `DARKGPT_LLM_MODEL`\n\n"
            "Nel frattempo restano disponibili: analisi statica del codice, "
            "controllo dello scope, gestione dei finding e generazione report."
        )
        if stream:
            return self._stream(text)
        return LlmResponse(content=text, model="mock", simulated=True)

    @staticmethod
    def _stream(text: str) -> Iterator[str]:
        for chunk in text.split(" "):
            yield chunk + " "
        yield "\n"


class OpenAICompatProvider:
    """Adattatore per API OpenAI-compatible."""

    name = "openai-compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # -- basso livello ---------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        return headers

    def _payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        return payload

    def _endpoint(self) -> str:
        base = self.settings.effective_llm_base_url.rstrip("/")
        return f"{base}/chat/completions"

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Esegue la richiesta con retry esponenziale e rispetto di Retry-After."""
        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                with httpx.Client(
                    timeout=self.settings.llm_timeout, trust_env=False
                ) as client:
                    response = client.post(
                        self._endpoint(),
                        json=payload,
                        headers=self._headers(),
                    )
                if response.status_code == 429:
                    delay = float(response.headers.get("Retry-After", 2**attempt))
                    logger.warning(
                        "llm_rate_limited",
                        extra={"extra_fields": {"delay": delay, "attempt": attempt}},
                    )
                    time.sleep(min(delay, 30))
                    continue
                if response.status_code >= 400:
                    raise ProviderError(
                        f"il provider ha risposto con HTTP {response.status_code}",
                        details={"body": redact(response.text[:2000])},
                    )
                return response.json()
            except ProviderError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.settings.llm_max_retries:
                    time.sleep(min(2**attempt, 20) + random.random())
                    continue
        raise ProviderError(
            f"impossibile contattare il provider LLM: {last_error}",
            details={"endpoint": self._endpoint()},
        )

    # -- API pubblica ----------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> LlmResponse | Iterator[str]:
        """Esegue la chat. Con `stream=True` restituisce un iteratore di token."""
        if stream:
            return self._stream(messages, tools)
        data = self._request(self._payload(messages, tools, stream=False))
        return self._parse_response(data)

    def _stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> Iterator[str]:
        """Restituisce i token della risposta in streaming (SSE)."""
        payload = self._payload(messages, tools, stream=True)
        try:
            with httpx.Client(
                timeout=self.settings.llm_timeout, trust_env=False
            ) as client:
                with client.stream(
                    "POST", self._endpoint(), json=payload, headers=self._headers()
                ) as response:
                    if response.status_code >= 400:
                        response.read()
                        raise ProviderError(
                            f"il provider ha risposto con HTTP {response.status_code}"
                        )
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        for choice in chunk.get("choices", []):
                            delta = choice.get("delta") or {}
                            content = delta.get("content")
                            if content:
                                yield content
        except ProviderError:
            raise
        except httpx.HTTPError as exc:
            raise ProviderError(f"errore di rete durante lo streaming: {exc}") from exc

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> LlmResponse:
        """Converte la risposta OpenAI-compatible nel formato interno."""
        choices = data.get("choices") or []
        if not choices:
            return LlmResponse(content="", model=data.get("model", ""))
        message = choices[0].get("message") or {}
        tool_calls: list[ToolCall] = []
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function") or {}
            arguments = function.get("arguments") or "{}"
            if isinstance(arguments, str):
                try:
                    parsed = json.loads(arguments)
                except json.JSONDecodeError:
                    parsed = {"_raw": arguments}
            else:
                parsed = dict(arguments)
            tool_calls.append(
                ToolCall(
                    id=str(raw_call.get("id", "")),
                    name=str(function.get("name", "")),
                    arguments=parsed,
                )
            )
        usage = data.get("usage") or {}
        return LlmResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            model=data.get("model", ""),
            simulated=False,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
            raw=data,
        )


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Restituisce il provider attivo in base alla configurazione.

    Senza endpoint configurato si usa il provider di fallback dichiarato:
    la piattaforma resta operativa e non effettua alcuna chiamata di rete.
    """
    settings = settings or get_settings()
    if not settings.llm_configured:
        return MockProvider(
            "DARKGPT_LLM_BASE_URL non e' impostata: impossibile contattare un provider."
        )
    return OpenAICompatProvider(settings)
