from __future__ import annotations

from typing import TypedDict


class NewsletterState(TypedDict):
    raw_articles: list[dict[str, object]]
    research_summary: str
    key_insights: str
    opinion_analysis: str
    final_newsletter: str
