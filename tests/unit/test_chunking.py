from app.ingestion.chunking import chunk_sections
from app.ingestion.loaders.base import RawSection


def test_chunk_sections_splits_long_text():
    section = RawSection(text="word " * 500, metadata={"page": 1})
    chunks = chunk_sections([section], chunk_size=200, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(chunk.metadata == {"page": 1} for chunk in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunk_sections_short_text_single_chunk():
    section = RawSection(text="a short sentence.")
    chunks = chunk_sections([section], chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 1
    assert chunks[0].text == "a short sentence."


def test_chunk_sections_preserves_per_section_metadata():
    sections = [
        RawSection(text="first section text", metadata={"page": 1}),
        RawSection(text="second section text", metadata={"page": 2}),
    ]
    chunks = chunk_sections(sections, chunk_size=1000, chunk_overlap=0)

    assert len(chunks) == 2
    assert chunks[0].metadata == {"page": 1}
    assert chunks[1].metadata == {"page": 2}
    assert chunks[1].index == 1


def test_chunk_sections_empty_input():
    assert chunk_sections([], chunk_size=100, chunk_overlap=10) == []
