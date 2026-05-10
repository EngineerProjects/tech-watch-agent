from __future__ import annotations

from app.config.settings import Settings
from app.delivery.newsletter_renderer import NewsletterRenderer


def test_renderer_generates_html() -> None:
    renderer = NewsletterRenderer(Settings(newsletter_title="Test Watch"))

    html = renderer.render_html("# Title\n\n**Hello** world", "Subject")

    assert "Test Watch" in html
    assert "<h1>Title</h1>" in html
    assert "Subject" in html


def test_renderer_generates_text_fallback() -> None:
    text = NewsletterRenderer.render_text("# Header\n\n**Body**")
    assert "Header" in text
    assert "Body" in text
