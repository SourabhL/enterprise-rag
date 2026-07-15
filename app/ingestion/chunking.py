from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingestion.loaders.base import RawSection

# Bump whenever chunk_size/chunk_overlap/splitter behavior changes -- ingestion
# compares this against a document's stored chunking_config_version to decide
# whether re-ingestion is needed even if content_hash is unchanged.
CHUNKING_CONFIG_VERSION = "v1"


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_sections(
    sections: list[RawSection], *, chunk_size: int, chunk_overlap: int
) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks: list[Chunk] = []
    for section in sections:
        for piece in splitter.split_text(section.text):
            chunks.append(Chunk(index=len(chunks), text=piece, metadata=section.metadata))
    return chunks
