from __future__ import annotations

from typing import TypedDict


class NewsletterState(TypedDict, total=False):
    raw_articles: list[dict[str, object]]
    research_summary: str
    key_insights: str
    opinion_analysis: str
    final_newsletter: str
    quality_score: float
    quality_factors: list[str]
    quality_routing: str
    error: str
