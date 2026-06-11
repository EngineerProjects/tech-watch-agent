import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from app.agents.base.base_agent import AgentResult
from app.api.models import NewsletterGenerateRequest
from app.api.routers.newsletter import generate_newsletter


@pytest.mark.asyncio
async def test_generate_newsletter_uses_orchestrator():
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(
        return_value=AgentResult.create_success(
            output={
                "report": "# AI Watch\n\nLatest updates",
                "email_sent": True,
                "research_results": [{"step_id": "s1"}, {"step_id": "s2"}, {"step_id": "s3"}],
            },
            metadata={"article_count": 3},
            session_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
    )

    with patch("app.agents.orchestrator.agent.OrchestratorAgent", return_value=mock_agent):
        response = await generate_newsletter(
            NewsletterGenerateRequest(topics=["AI"], send_email=True),
            BackgroundTasks(),
        )

    assert response.article_count == 3
    assert response.email_sent is True
    assert response.subject == "AI Watch"
    assert "AI Watch" in response.preview
