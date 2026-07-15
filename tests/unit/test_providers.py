from typing import Literal

from app.providers.base import EmbeddingProvider, LLMProvider, LLMResponse, Message, Usage


class FakeLLMProvider:
    model_name = "fake-llm"

    async def generate(
        self, *, system: str, messages: list[Message], max_tokens: int, effort: str = "high"
    ) -> LLMResponse:
        return LLMResponse(
            text=f"echo: {messages[-1].content}",
            usage=Usage(input_tokens=10, output_tokens=5),
        )

    async def stream(self, *, system: str, messages: list[Message], max_tokens: int):
        yield None


class FakeEmbeddingProvider:
    model_name = "fake-embed"
    dimensions = 4

    async def embed(
        self, texts: list[str], *, input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        return [[float(len(t))] * self.dimensions for t in texts]


def test_fake_llm_provider_conforms_to_protocol():
    assert isinstance(FakeLLMProvider(), LLMProvider)


def test_fake_embedding_provider_conforms_to_protocol():
    assert isinstance(FakeEmbeddingProvider(), EmbeddingProvider)


async def test_fake_llm_provider_generate():
    provider = FakeLLMProvider()
    response = await provider.generate(
        system="You are helpful.",
        messages=[Message(role="user", content="hello")],
        max_tokens=100,
    )
    assert response.text == "echo: hello"
    assert response.usage.input_tokens == 10


async def test_fake_embedding_provider_embed():
    provider = FakeEmbeddingProvider()
    vectors = await provider.embed(["ab", "abcd"], input_type="document")
    assert len(vectors) == 2
    assert len(vectors[0]) == provider.dimensions
    assert vectors[0] != vectors[1]
