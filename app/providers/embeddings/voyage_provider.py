from typing import Literal

import voyageai

from app.config import Settings


class VoyageEmbeddingProvider:
    def __init__(self, settings: Settings):
        self.model_name = settings.voyage_embedding_model
        self.dimensions = settings.voyage_embedding_dimensions
        self._client = voyageai.AsyncClient(api_key=settings.voyage_api_key)

    async def embed(
        self, texts: list[str], *, input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        result = await self._client.embed(
            texts, model=self.model_name, input_type=input_type
        )
        return [[float(x) for x in embedding] for embedding in result.embeddings]
