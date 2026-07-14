from io import BytesIO

from docx import Document as DocxDocument

from app.ingestion.loaders.base import RawSection


class DocxLoader:
    def supports(self, content_type: str) -> bool:
        return (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def load(self, raw: bytes) -> list[RawSection]:
        docx = DocxDocument(BytesIO(raw))
        text = "\n".join(p.text for p in docx.paragraphs if p.text.strip())
        return [RawSection(text=text)] if text.strip() else []
