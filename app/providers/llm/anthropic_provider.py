from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import (
    CacheControlEphemeralParam,
    MessageParam,
    OutputConfigParam,
    TextBlockParam,
)

from app.config import Settings
from app.core.exceptions import ProviderError
from app.providers.base import Effort, LLMResponse, LLMStreamEvent, Message, Usage

# System-prompt instructions are stable across requests and go before the cache
# breakpoint; the per-request retrieved context + question are appended after it
# by callers, so this prefix is what actually gets cached.
_CACHE_CONTROL: CacheControlEphemeralParam = {"type": "ephemeral"}


class AnthropicLLMProvider:
    def __init__(self, settings: Settings):
        self.model_name = settings.llm_model
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _build_messages(self, messages: list[Message]) -> list[MessageParam]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def _build_system(self, system: str) -> list[TextBlockParam]:
        return [{"type": "text", "text": system, "cache_control": _CACHE_CONTROL}]

    def _usage_from(self, sdk_usage: anthropic.types.Usage) -> Usage:
        return Usage(
            input_tokens=sdk_usage.input_tokens,
            output_tokens=sdk_usage.output_tokens,
            cache_read_input_tokens=sdk_usage.cache_read_input_tokens or 0,
            cache_creation_input_tokens=sdk_usage.cache_creation_input_tokens or 0,
        )

    async def generate(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int,
        effort: Effort = "high",
    ) -> LLMResponse:
        output_config: OutputConfigParam = {"effort": effort}
        try:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                system=self._build_system(system),
                messages=self._build_messages(messages),
                output_config=output_config,
            )
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {e}") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"Failed to reach Anthropic API: {e}") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Anthropic API error ({e.status_code}): {e.message}") from e

        text = next((block.text for block in response.content if block.type == "text"), "")
        return LLMResponse(
            text=text,
            usage=self._usage_from(response.usage),
            stop_reason=response.stop_reason,
        )

    async def stream(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int,
    ) -> AsyncIterator[LLMStreamEvent]:
        try:
            async with self._client.messages.stream(
                model=self.model_name,
                max_tokens=max_tokens,
                system=self._build_system(system),
                messages=self._build_messages(messages),
            ) as stream:
                async for text in stream.text_stream:
                    yield LLMStreamEvent(delta=text)

                final = await stream.get_final_message()
                yield LLMStreamEvent(
                    delta="",
                    is_final=True,
                    usage=self._usage_from(final.usage),
                )
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {e}") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"Failed to reach Anthropic API: {e}") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Anthropic API error ({e.status_code}): {e.message}") from e
