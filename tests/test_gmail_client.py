import pytest

from app.config.settings import Settings
from app.delivery.gmail_client import GmailDeliveryClient


class _FakeCreds:
    def __init__(self, *, valid: bool, expired: bool = False, refresh_token: str | None = None, token_json: str = '{"token":"new"}'):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self._token_json = token_json
        self.refreshed = False

    def refresh(self, request) -> None:
        self.valid = True
        self.expired = False
        self.refreshed = True

    def to_json(self) -> str:
        return self._token_json


def test_build_flow_prefers_runtime_credentials_json(monkeypatch):
    captured = {}

    def fake_from_client_config(payload, scopes):
        captured['payload'] = payload
        captured['scopes'] = scopes
        return 'runtime-flow'

    monkeypatch.setattr(
        'app.delivery.gmail_client.InstalledAppFlow.from_client_config',
        fake_from_client_config,
    )

    client = GmailDeliveryClient(
        Settings(gmail_credentials_json='{"installed": {"client_id": "abc"}}')
    )

    assert client._build_flow() == 'runtime-flow'
    assert captured['payload']['installed']['client_id'] == 'abc'
    assert captured['scopes'] == client.SCOPES


def test_load_credentials_prefers_db_token_over_file(monkeypatch):
    client = GmailDeliveryClient(Settings(gmail_token_json='{"token": "db"}'))
    creds = _FakeCreds(valid=True)

    monkeypatch.setattr(client, '_load_token_from_json', lambda: creds)
    monkeypatch.setattr(
        client,
        '_load_token_from_file',
        lambda: (_ for _ in ()).throw(AssertionError('file token should not be used')),
    )

    assert client._load_credentials() is creds


def test_load_credentials_refreshes_and_persists_runtime_token(monkeypatch):
    client = GmailDeliveryClient(Settings(gmail_token_json='{"token": "old"}'))
    creds = _FakeCreds(valid=False, expired=True, refresh_token='refresh-token')
    persisted: list[str] = []

    monkeypatch.setattr(client, '_load_token_from_json', lambda: creds)
    monkeypatch.setattr(client, '_load_token_from_file', lambda: None)
    monkeypatch.setattr(client, '_persist_token', lambda token_json: persisted.append(token_json))
    monkeypatch.setattr(
        client,
        '_build_flow',
        lambda: (_ for _ in ()).throw(AssertionError('oauth flow should not run when refresh is possible')),
    )

    assert client._load_credentials() is creds
    assert creds.refreshed is True
    assert persisted == ['{"token":"new"}']


def test_invalid_runtime_token_json_raises_value_error():
    client = GmailDeliveryClient(Settings(gmail_token_json='not-json'))

    with pytest.raises(ValueError):
        client._load_token_from_json()
