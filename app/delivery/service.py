from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.delivery.gmail_client import GmailDeliveryClient
from app.delivery.newsletter_renderer import NewsletterRenderer


logger = get_logger(__name__)


@dataclass(slots=True)
class DeliveryResult:
    subject: str
    html_content: str
    text_content: str
    sent: bool
    configured: bool
    message: str


class ReportDeliveryService:
    """Shared service for report rendering and optional email delivery."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        renderer: Optional[NewsletterRenderer] = None,
        gmail_client: Optional[GmailDeliveryClient] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._renderer = renderer or NewsletterRenderer(self.settings)
        self._gmail_client = gmail_client or GmailDeliveryClient(self.settings)

    def prepare(self, report: str, subject: str) -> DeliveryResult:
        html_content = self._renderer.render_html(report, subject)
        text_content = self._renderer.render_text(report)
        return DeliveryResult(
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            sent=False,
            configured=self.settings.has_email_delivery,
            message=f"Subject: {subject}\n\nReport prepared ({len(report)} chars)",
        )

    def deliver(self, report: str, subject: str, send: bool = True) -> DeliveryResult:
        prepared = self.prepare(report, subject)

        if not send:
            prepared.message = "Email delivery skipped by request"
            return prepared

        if not self.settings.has_email_delivery:
            prepared.message = "Email delivery not configured"
            return prepared

        try:
            sent = self._gmail_client.send_email(
                subject=prepared.subject,
                body_html=prepared.html_content,
                body_text=prepared.text_content,
            )
            prepared.sent = sent
            prepared.message = f"Email sent: {sent}"
            logger.info("Email delivery via shared service: %s", "success" if sent else "failed")
            return prepared
        except Exception as exc:
            logger.error("Shared email delivery failed: %s", exc)
            prepared.sent = False
            prepared.message = f"Email error: {exc}"
            return prepared
