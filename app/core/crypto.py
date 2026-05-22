"""
Symmetric encryption for sensitive config values stored in the database.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
The encryption key is read from the CONFIG_ENCRYPTION_KEY environment variable.

If no key is configured, values are stored and returned as plain text
(with a startup warning). This maintains backward compatibility.

Key generation (run once, paste result into .env):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os
from functools import lru_cache
from app.core.logging import get_logger

logger = get_logger(__name__)

# Fields that contain secrets and must be encrypted at rest.
SENSITIVE_FIELDS: frozenset[str] = frozenset({
    "llm_api_key",
    "tavily_api_key",
    "serper_api_key",
    "semantic_scholar_api_key",
    "github_api_token",
    "exa_api_key",
    "langsearch_api_key",
    "jina_api_key",
    "zai_api_key",
    "gmail_credentials_json",
    "gmail_token_json",
})

_ENC_PREFIX = "enc:"


@lru_cache(maxsize=1)
def _get_fernet():
    """Return a Fernet instance or None if no key is configured."""
    raw_key = os.getenv("CONFIG_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        logger.warning(
            "CONFIG_ENCRYPTION_KEY is not set — sensitive config values will be "
            "stored in plain text. Generate a key with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(raw_key.encode())
    except Exception as exc:
        logger.error("Invalid CONFIG_ENCRYPTION_KEY: %s", exc)
        return None


def encrypt_value(field: str, value: str) -> str:
    """Encrypt a value if the field is sensitive and a key is configured."""
    if field not in SENSITIVE_FIELDS or not value:
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    try:
        return _ENC_PREFIX + fernet.encrypt(value.encode()).decode()
    except Exception as exc:
        logger.warning("Failed to encrypt field '%s': %s", field, exc)
        return value


def decrypt_value(field: str, value: str) -> str:
    """Decrypt a value if it carries the encrypted prefix."""
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    try:
        return fernet.decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except Exception as exc:
        logger.warning("Failed to decrypt field '%s': %s — returning raw value", field, exc)
        return value


def is_encryption_active() -> bool:
    """Return whether Fernet encryption is available for sensitive config."""
    return _get_fernet() is not None


def decrypt_overrides(overrides: dict[str, str]) -> dict[str, str]:
    """Decrypt all values in a DB-override dict before applying them to Settings."""
    return {k: decrypt_value(k, v) for k, v in overrides.items()}
