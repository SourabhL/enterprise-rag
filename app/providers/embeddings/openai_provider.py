from typing import Literal

from openai import AsyncOpenAI

from app.config import Settings

# OpenAI's embeddings API has no document/query asymmetry (unlike Voyage) --
# input_type is accepted for interface conformance but otherwise unused.


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings):
        self.model_name = settings.openai_embedding_model
        self.dimensions = settings.openai_embedding_dimensions
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(
        self, texts: list[str], *, input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self.model_name, input=texts, dimensions=self.dimensions
        )
        return [item.embedding for item in response.data]
