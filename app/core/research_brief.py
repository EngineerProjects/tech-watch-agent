"""Helpers to build consistent research prompts and session titles."""

from __future__ import annotations

from typing import Optional


def build_research_brief(
    subject: str,
    topics: Optional[list[str]] = None,
    research_instructions: Optional[str] = None,
) -> str:
    """Build the persisted/orchestrated research brief from structured fields."""
    subject_clean = subject.strip()
    topics_clean = [topic.strip() for topic in (topics or []) if topic.strip()]
    instructions_clean = (research_instructions or "").strip()

    parts = [f"Subject:\n{subject_clean}"]
    if topics_clean:
        parts.append(f"Topics:\n{', '.join(topics_clean)}")
    if instructions_clean:
        parts.append(f"Research Instructions:\n{instructions_clean}")

    return "\n\n".join(parts)


def derive_session_title(
    *,
    title: Optional[str] = None,
    subject: Optional[str] = None,
    task: Optional[str] = None,
    max_length: int = 96,
) -> str:
    """Derive a short display title without losing the full prompt in storage."""
    candidate = (title or subject or task or "Nouvelle session").strip()
    if len(candidate) <= max_length:
        return candidate
    return candidate[: max_length - 3].rstrip() + "..."
