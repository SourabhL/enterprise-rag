from app.ingestion.loaders.base import DocumentLoader, UnsupportedContentTypeError
from app.ingestion.loaders.docx_loader import DocxLoader
from app.ingestion.loaders.html_loader import HtmlLoader
from app.ingestion.loaders.pdf_loader import PdfLoader
from app.ingestion.loaders.txt_loader import TxtLoader

_LOADERS: list[DocumentLoader] = [TxtLoader(), HtmlLoader(), PdfLoader(), DocxLoader()]

SUPPORTED_CONTENT_TYPES = (
    "text/plain",
    "text/markdown",
    "text/html",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


def get_loader(content_type: str) -> DocumentLoader:
    for loader in _LOADERS:
        if loader.supports(content_type):
            return loader
    raise UnsupportedContentTypeError(f"No loader registered for content type: {content_type}")
