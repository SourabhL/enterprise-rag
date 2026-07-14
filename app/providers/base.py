from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["user", "assistant"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: Usage
    stop_reason: str | None = None


@dataclass(frozen=True)
class LLMStreamEvent:
    """A single incremental piece of a streamed generation."""

    delta: str
    is_final: bool = False
    usage: Usage | None = None  # set only on the final event


@runtime_checkable
class LLMProvider(Protocol):
    model_name: str

    async def generate(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int,
        effort: Effort = "high",
    ) -> LLMResponse: ...

    def stream(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int,
    ) -> AsyncIterator[LLMStreamEvent]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    async def embed(
        self, texts: list[str], *, input_type: Literal["document", "query"]
    ) -> list[list[float]]: ...
