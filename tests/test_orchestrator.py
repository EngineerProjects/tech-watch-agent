from __future__ import annotations

from app.config.settings import Settings
from app.scheduler.service import OrchestratorScheduler


def test_subject_extraction_prefers_embedded_subject() -> None:
    orchestrator = OrchestratorScheduler(settings=Settings(llm_api_key="test"))

    subject = orchestrator._extract_subject("Subject: Weekly AI Watch\n\nContent")

    assert subject == "Weekly AI Watch"
