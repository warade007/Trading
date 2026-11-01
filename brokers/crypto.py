import json

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from config.local_secrets import broker_keys, LocalKeyError
from .errors import BrokerError


@sensitive_variables()
def keyring():
    try:
        keys = settings.BROKER_FERNET_KEYS
        if keys is None:
            keys = broker_keys()
        if not isinstance(keys, (list, tuple)) or not 1 <= len(keys) <= 32:
            raise ValueError
        if settings.SECRET_KEY in keys:
            raise ValueError
        return MultiFernet([Fernet(key.encode("ascii")) for key in keys])
    except (LocalKeyError, ValueError, TypeError, AttributeError, UnicodeError):
        raise BrokerError("KEY_UNAVAILABLE") from None


@sensitive_variables()
def encrypt(value, purpose):
    if not isinstance(value, str) or not value:
        raise BrokerError("INVALID_INPUT")
    return "v1:" + keyring().encrypt(json.dumps({"purpose": purpose, "value": value}).encode()).decode()


@sensitive_variables()
def decrypt(ciphertext, purpose):
    try:
        if not ciphertext.startswith("v1:"):
            raise ValueError
        payload = json.loads(keyring().decrypt(ciphertext[3:].encode()))
        if payload["purpose"] != purpose or not isinstance(payload["value"], str) or not payload["value"]:
            raise ValueError
        return payload["value"]
    except (InvalidToken, ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise BrokerError("KEY_UNAVAILABLE") from None


def require_envelope(value):
    if value and not value.startswith("v1:gAAAA"):
        raise BrokerError("KEY_UNAVAILABLE")
