from __future__ import annotations

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class GmailDeliveryClient:
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._service = None

    def send_email(self, subject: str, body_html: str, body_text: str) -> bool:
        if not self.settings.has_email_delivery:
            logger.error("Email delivery is not configured")
            return False

        try:
            service = self._get_service()
            message = self._create_message(
                recipients=self.settings.recipient_emails,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            service.users().messages().send(userId="me", body=message).execute()
            logger.info(
                "Newsletter sent to %s recipients",
                len(self.settings.recipient_emails),
            )
            return True
        except (HttpError, OSError, ValueError) as exc:
            logger.error("Failed to send Gmail message: %s", exc)
            return False

    def _get_service(self):
        if self._service is not None:
            return self._service

        credentials = self._load_credentials()
        self._service = build("gmail", "v1", credentials=credentials)
        return self._service

    def _load_credentials(self) -> Credentials:
        token_path = Path(self.settings.gmail_token_path)
        credentials_path = Path(self.settings.gmail_credentials_path)

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

        if not credentials_path.exists():
            raise ValueError(f"Gmail credentials file not found: {credentials_path}")

        # The first run performs the local OAuth handshake and persists the token
        # so scheduled runs can send email non-interactively afterward.
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.SCOPES)
        creds = flow.run_local_server(port=8090)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _create_message(
        self,
        recipients: list[str],
        subject: str,
        body_html: str,
        body_text: str,
    ) -> dict[str, str]:
        message = MIMEMultipart("alternative")
        message["to"] = ", ".join(recipients)
        message["from"] = self.settings.sender_email
        message["subject"] = subject
        message.attach(MIMEText(body_text, "plain"))
        message.attach(MIMEText(body_html, "html"))

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return {"raw": raw_message}
