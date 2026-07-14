from io import BytesIO

from pypdf import PdfReader

from app.ingestion.loaders.base import RawSection


class PdfLoader:
    def supports(self, content_type: str) -> bool:
        return content_type == "application/pdf"

    def load(self, raw: bytes) -> list[RawSection]:
        reader = PdfReader(BytesIO(raw))
        sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                sections.append(RawSection(text=text, metadata={"page": page_number}))
        return sections
