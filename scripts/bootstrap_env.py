"""Create a local .env without placing real secrets in the repository."""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"


def generated_values() -> dict[str, str]:
    return {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "OBJECT_STORAGE_SECRET_KEY": secrets.token_urlsafe(32),
        "SESSION_SECRET": secrets.token_urlsafe(48),
        "FIELD_ENCRYPTION_KEY": base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode(),
    }


def replace_value(text: str, key: str, value: str) -> str:
    lines: list[str] = []
    replaced = False
    for line in text.splitlines():
        if line.startswith(f"{key}="):
            lines.append(f"{key}={value}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        raise RuntimeError(f"{key} is missing from .env.example")
    return "\n".join(lines) + "\n"


def main() -> int:
    if TARGET.exists():
        print(".env already exists; it was not overwritten.")
        return 1
    text = EXAMPLE.read_text(encoding="utf-8")
    values = generated_values()
    for key, value in values.items():
        text = replace_value(text, key, value)
    text = text.replace(
        "REPLACE_WITH_GENERATED_SECRET",
        values["POSTGRES_PASSWORD"],
        2,
    )
    TARGET.write_text(text, encoding="utf-8")
    try:
        os.chmod(TARGET, 0o600)
    except OSError:
        pass
    print("Created .env with local infrastructure secrets.")
    print("Add OPENAI_API_KEY only if you want live AI-generated answers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
