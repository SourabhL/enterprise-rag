from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class GoldenExample:
    question: str
    document_text: str
    document_filename: str = "eval-doc.txt"
    expected_facts: list[str] = field(default_factory=list)


def load_golden_dataset(path: Path) -> list[GoldenExample]:
    raw = yaml.safe_load(path.read_text())
    return [GoldenExample(**item) for item in raw]
