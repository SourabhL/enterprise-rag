from app.ingestion.hashing import content_hash


def test_content_hash_deterministic():
    assert content_hash(b"hello world") == content_hash(b"hello world")


def test_content_hash_differs_for_different_content():
    assert content_hash(b"hello") != content_hash(b"world")


def test_content_hash_is_sha256_hex():
    digest = content_hash(b"hello world")
    assert len(digest) == 64
    int(digest, 16)  # raises ValueError if not valid hex
