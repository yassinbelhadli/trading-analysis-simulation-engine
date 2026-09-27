import base64
import os

from cryptography.fernet import Fernet
from config.settings import ENCRYPTION_KEY


def _get_cipher() -> Fernet:
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY is not set in .env")
    key = _normalise_key(ENCRYPTION_KEY)
    return Fernet(key)


def _normalise_key(raw: str) -> bytes:
    key = raw.strip()
    try:
        base64.urlsafe_b64decode(key)
        return key.encode("utf-8")
    except Exception:
        pass
    if len(key) < 32:
        key = key.ljust(32, "=")
    key_bytes = key[:32].encode("utf-8").ljust(32, b"=")
    return base64.urlsafe_b64encode(key_bytes)


def encrypt(plain_text: str) -> str:
    cipher = _get_cipher()
    token = cipher.encrypt(plain_text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(token: str) -> str:
    cipher = _get_cipher()
    return cipher.decrypt(token.encode("utf-8")).decode("utf-8")


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")
