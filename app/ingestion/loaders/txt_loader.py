from app.ingestion.loaders.base import RawSection


class TxtLoader:
    def supports(self, content_type: str) -> bool:
        return content_type in ("text/plain", "text/markdown")

    def load(self, raw: bytes) -> list[RawSection]:
        text = raw.decode("utf-8", errors="replace")
        return [RawSection(text=text)]
