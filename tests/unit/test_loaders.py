from app.ingestion.loaders.html_loader import HtmlLoader
from app.ingestion.loaders.registry import get_loader
from app.ingestion.loaders.txt_loader import TxtLoader


def test_txt_loader_supports_and_loads():
    loader = TxtLoader()
    assert loader.supports("text/plain")
    assert not loader.supports("application/pdf")

    sections = loader.load(b"hello world")
    assert len(sections) == 1
    assert sections[0].text == "hello world"


def test_html_loader_strips_tags_and_scripts():
    loader = HtmlLoader()
    raw = b"<html><body><script>evil()</script><p>Hello</p><p>World</p></body></html>"
    sections = loader.load(raw)

    assert len(sections) == 1
    assert "evil()" not in sections[0].text
    assert "Hello" in sections[0].text
    assert "World" in sections[0].text


def test_get_loader_selects_by_content_type():
    assert isinstance(get_loader("text/plain"), TxtLoader)
    assert isinstance(get_loader("text/html"), HtmlLoader)
