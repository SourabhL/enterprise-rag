from app.core.security import generate_api_key, hash_api_key


def test_generate_api_key_roundtrip():
    raw_key, prefix, key_hash = generate_api_key()

    assert raw_key.startswith("erag_")
    assert raw_key.startswith(prefix)
    assert len(prefix) == 8
    assert hash_api_key(raw_key) == key_hash


def test_generate_api_key_is_unique():
    _, _, hash1 = generate_api_key()
    _, _, hash2 = generate_api_key()

    assert hash1 != hash2


def test_hash_api_key_is_deterministic():
    raw_key, _, _ = generate_api_key()

    assert hash_api_key(raw_key) == hash_api_key(raw_key)
