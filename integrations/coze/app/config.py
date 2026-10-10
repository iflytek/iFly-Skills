"""Explicit, immutable backend grants; no credentials are changed per request."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import os
from pathlib import Path

from .catalog import SKILL_IDS


SITES = ("cn", "global")
SITE_FIELDS = ("API_BASE_URL", "WORKSPACE_ID", "API_TOKEN", "BACKEND_BASE_URL", "BACKEND_API_KEY", "ALLOWED_SKILLS")
CONFIG_KEYS = frozenset({"COZE_ENABLED_SITES"} | {
    f"COZE_{site.upper()}_{suffix}" for site in SITES for suffix in SITE_FIELDS
})


class ConfigurationError(ValueError):
    """Contains only field names or fixed messages, never configuration values."""


def read_config(path: Path) -> dict[str, str]:
    """Read literal KEY=VALUE lines; reject unknown/duplicate keys, no expansion."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise ConfigurationError("Cannot read configuration file as UTF-8") from None
    values = {}
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or key not in CONFIG_KEYS or key in values:
            raise ConfigurationError(f"Invalid or duplicate configuration key on line {number}")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigurationError(f"Unclosed quoted value on line {number}")
            value = value[1:-1]
        values[key] = value
    return values


@dataclass(frozen=True)
class Principal:
    site: str
    workspace_id: str = field(repr=False)
    allowed_skills: frozenset[str]


@dataclass(frozen=True)
class SiteGrant:
    principal: Principal
    api_key: str = field(repr=False)

    def __post_init__(self):
        principal = self.principal
        if principal.site not in SITES:
            raise ConfigurationError("Unknown enabled Coze site")
        prefix = f"COZE_{principal.site.upper()}_"
        if not principal.workspace_id.strip():
            raise ConfigurationError(f"Missing {prefix}WORKSPACE_ID")
        if (not isinstance(principal.allowed_skills, frozenset) or not principal.allowed_skills
                or not principal.allowed_skills <= SKILL_IDS):
            raise ConfigurationError(f"{prefix}ALLOWED_SKILLS must list known Skill IDs")
        if not 32 <= len(self.api_key) <= 256 or any(not 33 <= ord(c) <= 126 for c in self.api_key):
            raise ConfigurationError(f"{prefix}BACKEND_API_KEY requires 32-256 printable ASCII characters without spaces")


@dataclass(frozen=True)
class Settings:
    grants: tuple[SiteGrant, ...]

    def __post_init__(self):
        if not isinstance(self.grants, tuple) or not self.grants:
            raise ConfigurationError("At least one site must be explicitly enabled")
        if len({grant.principal.site for grant in self.grants}) != len(self.grants):
            raise ConfigurationError("Duplicate enabled Coze site")
        if len({grant.api_key for grant in self.grants}) != len(self.grants):
            raise ConfigurationError("The two sites must use separate backend service keys")


def load_settings(*, env_file: Path | None = None, environ: Mapping[str, str] | None = None) -> Settings:
    environment = os.environ if environ is None else environ
    if env_file is None and environment.get("COZE_ENV_FILE"):
        env_file = Path(environment["COZE_ENV_FILE"])
    values = read_config(env_file) if env_file is not None else {}
    # An explicitly empty process variable overrides the file and fails validation.
    values.update({key: environment[key] for key in CONFIG_KEYS if key in environment})
    sites = tuple(part.strip() for part in values.get("COZE_ENABLED_SITES", "").split(","))
    if not sites or any(site not in SITES for site in sites):
        raise ConfigurationError("COZE_ENABLED_SITES must explicitly select cn, global, or cn,global")
    grants = []
    for site in sites:
        prefix = f"COZE_{site.upper()}_"
        allowed = frozenset(part.strip() for part in values.get(prefix + "ALLOWED_SKILLS", "").split(","))
        grant = SiteGrant(
            principal=Principal(site, values.get(prefix + "WORKSPACE_ID", ""), allowed),
            api_key=values.get(prefix + "BACKEND_API_KEY", ""),
        )
        if grant.api_key in {values.get("COZE_CN_API_TOKEN"), values.get("COZE_GLOBAL_API_TOKEN")}:
            raise ConfigurationError("A platform token must not be reused as a backend service key")
        grants.append(grant)
    # API tokens, upstream credentials and deployment URLs are not kept in backend settings.
    return Settings(tuple(grants))
