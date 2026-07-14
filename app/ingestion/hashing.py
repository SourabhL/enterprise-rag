import hashlib


def content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
