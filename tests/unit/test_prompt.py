import uuid

from app.retrieval.prompt import build_context_block, build_user_message, extract_citations
from app.vectorstore.base import ScoredChunk


def _chunk(text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), text=text, score=0.9, metadata={}
    )


def test_build_context_block_numbers_sources():
    chunks = [_chunk("first"), _chunk("second")]
    block = build_context_block(chunks)

    assert "[S1]\nfirst" in block
    assert "[S2]\nsecond" in block


def test_build_user_message_with_no_chunks():
    message = build_user_message("What is X?", [])
    assert "(none found)" in message
    assert "What is X?" in message


def test_build_user_message_includes_context_and_question():
    chunks = [_chunk("relevant fact")]
    message = build_user_message("What is X?", chunks)

    assert "relevant fact" in message
    assert "What is X?" in message


def test_extract_citations_matches_cited_sources_only():
    chunks = [_chunk("fact one"), _chunk("fact two"), _chunk("fact three")]
    answer = "The answer relies on [S1] and [S3]."

    citations = extract_citations(answer, chunks)

    assert len(citations) == 2
    cited_texts = {c.snippet for c in citations}
    assert cited_texts == {"fact one", "fact three"}


def test_extract_citations_no_citations_in_answer():
    chunks = [_chunk("fact one")]
    assert extract_citations("No sources cited here.", chunks) == []


def test_extract_citations_ignores_out_of_range_index():
    chunks = [_chunk("only one chunk")]
    # [S5] doesn't correspond to any retrieved chunk -- should be silently ignored.
    assert extract_citations("See [S5].", chunks) == []
