"""Map one canonical credential set onto each checked-in skill script."""

from __future__ import annotations

import os
from collections.abc import Mapping

CANONICAL_APP_ID = "IFLYTEK_APP_ID"
CANONICAL_API_KEY = "IFLYTEK_API_KEY"
CANONICAL_API_SECRET = "IFLYTEK_API_SECRET"
CANONICAL_CREDENTIALS = (
    CANONICAL_APP_ID,
    CANONICAL_API_KEY,
    CANONICAL_API_SECRET,
)

_PREFIX_PROFILES = {
    "xfei": "XFEI",
    "xfyun": "XFYUN",
    "ifly": "IFLY",
}


class CredentialError(RuntimeError):
    """Raised when a tool cannot obtain its required credentials."""


def _lookup(canonical: str, overrides: Mapping[str, str] | None) -> str | None:
    if overrides and overrides.get(canonical):
        return overrides[canonical]
    return os.environ.get(canonical)


def resolve_env(
    cred_profile: str,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return only the script-specific credential variables for a subprocess.

    The canonical values come from MCPB/Smithery user configuration or the
    server process environment. Values are never included in errors.
    """
    if cred_profile == "none":
        return {}

    prefix = _PREFIX_PROFILES.get(cred_profile)
    if prefix is None:
        raise CredentialError(f"Unknown credential profile: {cred_profile}")

    values = {
        CANONICAL_APP_ID: _lookup(CANONICAL_APP_ID, overrides),
        CANONICAL_API_KEY: _lookup(CANONICAL_API_KEY, overrides),
        CANONICAL_API_SECRET: _lookup(CANONICAL_API_SECRET, overrides),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise CredentialError("Missing required credentials: " + ", ".join(missing))

    return {
        f"{prefix}_APP_ID": values[CANONICAL_APP_ID],
        f"{prefix}_API_KEY": values[CANONICAL_API_KEY],
        f"{prefix}_API_SECRET": values[CANONICAL_API_SECRET],
    }
