from app.config.settings import Settings
from app.delivery.service import ReportDeliveryService


class _FakeRenderer:
    def render_html(self, report: str, subject: str) -> str:
        return f"<h1>{subject}</h1><p>{report}</p>"

    def render_text(self, report: str) -> str:
        return report


class _FailingGmailClient:
    def send_email(self, subject: str, body_html: str, body_text: str) -> bool:
        raise AssertionError("send_email should not have been called")


class _SuccessfulGmailClient:
    def __init__(self) -> None:
        self.calls = []

    def send_email(self, subject: str, body_html: str, body_text: str) -> bool:
        self.calls.append((subject, body_html, body_text))
        return True


def test_prepare_returns_rendered_preview():
    settings = Settings()
    service = ReportDeliveryService(
        settings=settings,
        renderer=_FakeRenderer(),
        gmail_client=_FailingGmailClient(),
    )

    result = service.prepare("# Report", "Tech Watch")

    assert result.subject == "Tech Watch"
    assert result.sent is False
    assert result.configured is False
    assert "<h1>Tech Watch</h1>" in result.html_content
    assert result.text_content == "# Report"


def test_deliver_skips_when_send_disabled():
    settings = Settings(
        sender_email="sender@example.com",
        recipient_emails=["dest@example.com"],
    )
    service = ReportDeliveryService(
        settings=settings,
        renderer=_FakeRenderer(),
        gmail_client=_FailingGmailClient(),
    )

    result = service.deliver("# Report", "Tech Watch", send=False)

    assert result.sent is False
    assert result.configured is True
    assert result.message == "Email delivery skipped by request"


def test_deliver_sends_when_configured():
    gmail = _SuccessfulGmailClient()
    settings = Settings(
        sender_email="sender@example.com",
        recipient_emails=["dest@example.com"],
    )
    service = ReportDeliveryService(
        settings=settings,
        renderer=_FakeRenderer(),
        gmail_client=gmail,
    )

    result = service.deliver("# Report", "Tech Watch", send=True)

    assert result.sent is True
    assert result.configured is True
    assert result.message == "Email sent: True"
    assert len(gmail.calls) == 1
