from __future__ import annotations

import base64
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings, get_settings
from app.core.crypto import encrypt_value, is_encryption_active
from app.core.logging import get_logger
from app.db.models import AppConfig


logger = get_logger(__name__)


@lru_cache(maxsize=4)
def _get_sync_session_factory(database_sync_url: str):
    engine = create_engine(database_sync_url, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


class GmailDeliveryClient:
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._service = None

    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: list[str] | None = None,
    ) -> bool:
        resolved_recipients = [
            email.strip()
            for email in (recipients if recipients is not None else self.settings.recipient_emails)
            if email and email.strip()
        ]
        if not self.settings.sender_email or not resolved_recipients:
            logger.error("Email delivery is not configured")
            return False

        try:
            service = self._get_service()
            message = self._create_message(
                recipients=resolved_recipients,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            service.users().messages().send(userId="me", body=message).execute()
            logger.info(
                "Newsletter sent to %s recipients",
                len(resolved_recipients),
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
        creds = self._load_token_from_json() or self._load_token_from_file()

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._persist_token(creds.to_json())
            return creds

        flow = self._build_flow()
        creds = flow.run_local_server(port=8090)
        self._persist_token(creds.to_json())
        return creds

    def _load_token_from_json(self) -> Credentials | None:
        raw = self.settings.gmail_token_json.strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid Gmail token JSON in runtime config") from exc
        return Credentials.from_authorized_user_info(payload, self.SCOPES)

    def _load_token_from_file(self) -> Credentials | None:
        token_path = Path(self.settings.gmail_token_path)
        if not token_path.exists():
            return None
        return Credentials.from_authorized_user_file(token_path, self.SCOPES)

    def _build_flow(self) -> InstalledAppFlow:
        raw = self.settings.gmail_credentials_json.strip()
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid Gmail credentials JSON in runtime config") from exc
            return InstalledAppFlow.from_client_config(payload, self.SCOPES)

        credentials_path = Path(self.settings.gmail_credentials_path)
        if not credentials_path.exists():
            raise ValueError(
                "Gmail OAuth is not configured. Save gmail_credentials_json in Settings "
                f"or mount the legacy credentials file at {credentials_path}."
            )

        return InstalledAppFlow.from_client_secrets_file(credentials_path, self.SCOPES)

    def _persist_token(self, token_json: str) -> None:
        if not token_json:
            return

        using_db_storage = bool(
            self.settings.gmail_credentials_json.strip() or self.settings.gmail_token_json.strip()
        )
        self.settings.gmail_token_json = token_json

        if using_db_storage:
            self._persist_token_json(token_json)

        token_path = self.settings.gmail_token_path.strip()
        if token_path:
            self._persist_token_file(token_path, token_json)

    def _persist_token_json(self, token_json: str) -> None:
        if (
            self.settings.app_env.lower() in {"production", "staging"}
            and not is_encryption_active()
        ):
            logger.warning(
                "Skipping Gmail token DB persistence because CONFIG_ENCRYPTION_KEY is missing"
            )
            return

        try:
            session_factory = _get_sync_session_factory(self.settings.database_sync_url)
            with session_factory() as session:
                record = session.get(AppConfig, "gmail_token_json")
                stored = encrypt_value("gmail_token_json", token_json)
                if record is None:
                    session.add(AppConfig(key="gmail_token_json", value=stored))
                else:
                    record.value = stored
                session.commit()
        except Exception as exc:
            logger.warning("Could not persist Gmail token to runtime config DB: %s", exc)

    def _persist_token_file(self, token_path: str, token_json: str) -> None:
        try:
            path = Path(token_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(token_json, encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist Gmail token to %s: %s", token_path, exc)

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
