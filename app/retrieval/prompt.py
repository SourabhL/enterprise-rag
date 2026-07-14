import re
import uuid
from dataclasses import dataclass

from app.vectorstore.base import ScoredChunk

SYSTEM_PROMPT = (
    "You are a retrieval-augmented question-answering assistant. Answer the "
    "user's question using ONLY the information in the provided sources. Cite "
    "every factual claim with the matching source tag, e.g. [S1] or [S2][S3] for "
    "multiple sources. If the sources do not contain the answer, say so plainly "
    "rather than guessing."
)

_CITATION_PATTERN = re.compile(r"\[S(\d+)\]")
_SNIPPET_LENGTH = 280


@dataclass(frozen=True)
class Citation:
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    snippet: str


def build_context_block(chunks: list[ScoredChunk]) -> str:
    return "\n\n".join(f"[S{i}]\n{chunk.text}" for i, chunk in enumerate(chunks, start=1))


def build_user_message(query: str, chunks: list[ScoredChunk]) -> str:
    if not chunks:
        return f"Sources: (none found)\n\nQuestion: {query}"
    return f"Sources:\n{build_context_block(chunks)}\n\nQuestion: {query}"


def extract_citations(answer: str, chunks: list[ScoredChunk]) -> list[Citation]:
    cited_indices = {int(m) for m in _CITATION_PATTERN.findall(answer)}
    return [
        Citation(
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            snippet=chunk.text[:_SNIPPET_LENGTH],
        )
        for i, chunk in enumerate(chunks, start=1)
        if i in cited_indices
    ]
