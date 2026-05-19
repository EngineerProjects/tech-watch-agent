from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from app.agents.base.base_agent import AgentResult
from app.api.models import NewsletterGenerateRequest
from app.api.routers.newsletter import generate_newsletter


@pytest.mark.asyncio
async def test_generate_newsletter_uses_shared_delivery_service():
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(
        return_value=AgentResult.create_success(
            output={
                "newsletter": "# AI Watch\n\nLatest updates",
                "subject": "AI Watch",
            },
            metadata={"article_count": 3},
        )
    )
    delivery_result = SimpleNamespace(sent=True, message="Email sent: True")

    with patch("app.api.routers.newsletter.create_newsletter_agent", return_value=mock_agent), \
         patch("app.api.routers.newsletter.ReportDeliveryService") as delivery_service_cls:
        delivery_service_cls.return_value.deliver.return_value = delivery_result

        response = await generate_newsletter(
            NewsletterGenerateRequest(topics=["AI"], send_email=True),
            BackgroundTasks(),
        )

    assert response.article_count == 3
    assert response.email_sent is True
    assert response.delivery_message == "Email sent: True"
    delivery_service_cls.return_value.deliver.assert_called_once_with(
        report="# AI Watch\n\nLatest updates",
        subject="AI Watch",
        send=True,
    )
