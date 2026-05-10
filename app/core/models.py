from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Article:
    title: str
    summary: str
    url: str
    topic: str
    published_date: str | None = None
    content: str = ""
    source: str = ""
    relevance_score: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class NewsletterRunResult:
    subject: str
    markdown_content: str
    html_content: str
    articles: list[Article] = field(default_factory=list)
