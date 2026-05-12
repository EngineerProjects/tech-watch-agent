"""
Email delivery tool.

This tool wraps the GmailDeliveryClient to provide email sending
capabilities as a registered tool in the agent's tool registry.
"""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.delivery.gmail_client import GmailDeliveryClient
from app.delivery.newsletter_renderer import NewsletterRenderer
from app.config.settings import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class EmailTool(BaseTool):
    """Tool for sending emails via Gmail.

    This tool handles email composition and delivery using Gmail API.
    It supports both HTML and plain text formats.

    Parameters:
        subject: Email subject line
        report: The report content (markdown) to send
        recipients: Optional list of recipient emails (uses config if not provided)

    Example:
        tool = EmailTool()
        result = await tool.execute({
            "subject": "Tech Watch Report",
            "report": "# Report\\n\\nContent here...",
        })
    """

    @property
    def name(self) -> str:
        return "email"

    @property
    def description(self) -> str:
        return "Send emails via Gmail. Accepts report content and sends to configured recipients."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.API

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "report": {
                    "type": "string",
                    "description": "Report content in markdown format",
                },
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of recipient emails",
                },
            },
            "required": ["subject", "report"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        subject = params.get("subject", "Tech Watch Report")
        report = params.get("report", "")
        recipients_override = params.get("recipients")

        if not report:
            return {
                "success": False,
                "data": None,
                "error": "No report content provided",
                "metadata": {},
            }

        settings = get_settings()

        if not settings.has_email_delivery:
            logger.warning("Email delivery not configured, returning prepared content")
            return {
                "success": True,
                "data": {
                    "sent": False,
                    "reason": "Email delivery not configured",
                    "subject": subject,
                    "prepared": True,
                    "recipients": recipients_override or settings.recipient_emails,
                },
                "error": None,
                "metadata": {
                    "content_length": len(report),
                    "configured": False,
                },
            }

        try:
            renderer = NewsletterRenderer(settings)
            html_content = renderer.render_html(report, subject)
            text_content = renderer.render_text(report)

            recipients = recipients_override or settings.recipient_emails

            gmail = GmailDeliveryClient(settings)
            sent = gmail.send_email(
                subject=subject,
                body_html=html_content,
                body_text=text_content,
            )

            if sent:
                logger.info("Email sent to %d recipients", len(recipients))
                return {
                    "success": True,
                    "data": {
                        "sent": True,
                        "subject": subject,
                        "recipients": recipients,
                        "recipient_count": len(recipients),
                    },
                    "error": None,
                    "metadata": {
                        "content_length": len(report),
                        "html_length": len(html_content),
                        "configured": True,
                    },
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": "Failed to send email via Gmail",
                    "metadata": {"configured": True},
                }

        except Exception as exc:
            logger.error("EmailTool execution failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Email delivery failed: {str(exc)}",
                "metadata": {},
            }


class EmailPreviewTool(BaseTool):
    """Tool for previewing email content without sending.

    Useful for testing and validation before actual delivery.

    Parameters:
        subject: Email subject line
        report: The report content (markdown) to preview

    Returns:
        HTML and text versions of the email for preview.
    """

    @property
    def name(self) -> str:
        return "email_preview"

    @property
    def description(self) -> str:
        return "Preview email content without sending. Returns HTML and text versions."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "report": {
                    "type": "string",
                    "description": "Report content in markdown format",
                },
            },
            "required": ["subject", "report"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        subject = params.get("subject", "Tech Watch Report")
        report = params.get("report", "")

        if not report:
            return {
                "success": False,
                "data": None,
                "error": "No report content provided",
                "metadata": {},
            }

        try:
            settings = get_settings()
            renderer = NewsletterRenderer(settings)

            html_content = renderer.render_html(report, subject)
            text_content = renderer.render_text(report)

            return {
                "success": True,
                "data": {
                    "subject": subject,
                    "html": html_content,
                    "text": text_content,
                    "html_length": len(html_content),
                    "text_length": len(text_content),
                },
                "error": None,
                "metadata": {
                    "content_length": len(report),
                },
            }

        except Exception as exc:
            logger.error("EmailPreviewTool execution failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Preview generation failed: {str(exc)}",
                "metadata": {},
            }
