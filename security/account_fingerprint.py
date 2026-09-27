import hashlib


def normalize_platform(value: str) -> str:
    return (value or "").strip().upper()


def normalize_server(value: str) -> str:
    return "".join((value or "").strip().upper().split())


def normalize_login(value: str | int) -> str:
    return str(value).strip()


def build_account_fingerprint(
    platform: str,
    server: str,
    login: str | int,
) -> str:
    raw = "|".join([
        normalize_platform(platform),
        normalize_server(server),
        normalize_login(login),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
