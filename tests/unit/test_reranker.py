import uuid

from app.retrieval.reranker import NoOpReranker, Reranker
from app.vectorstore.base import ScoredChunk


async def test_noop_reranker_returns_chunks_unchanged():
    chunks = [
        ScoredChunk(chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), text="a", score=0.5),
        ScoredChunk(chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), text="b", score=0.9),
    ]

    result = await NoOpReranker().rerank("some query", chunks)

    assert result == chunks


def test_noop_reranker_conforms_to_protocol():
    assert isinstance(NoOpReranker(), Reranker)
