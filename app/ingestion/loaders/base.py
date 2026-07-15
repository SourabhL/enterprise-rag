from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RawSection:
    text: str
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class DocumentLoader(Protocol):
    def supports(self, content_type: str) -> bool: ...

    def load(self, raw: bytes) -> list[RawSection]: ...


class UnsupportedContentTypeError(ValueError):
    pass
