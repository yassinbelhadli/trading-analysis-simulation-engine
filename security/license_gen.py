from __future__ import annotations

import secrets
import string


def generate_license_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    parts = ["ICT"]
    for _ in range(3):
        parts.append("".join(secrets.choice(alphabet) for _ in range(4)))
    return "-".join(parts)
