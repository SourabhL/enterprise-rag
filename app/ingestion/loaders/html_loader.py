from bs4 import BeautifulSoup

from app.ingestion.loaders.base import RawSection


class HtmlLoader:
    def supports(self, content_type: str) -> bool:
        return content_type == "text/html"

    def load(self, raw: bytes) -> list[RawSection]:
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return [RawSection(text=text)]
