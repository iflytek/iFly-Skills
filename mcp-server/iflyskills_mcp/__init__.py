"""iFLYTEK skills exposed as a Model Context Protocol server."""

from .credentials import CredentialError, resolve_env
from .registry import Skill, SkillArg, SkillEntry, get_skill, load_registry, repo_root
from .runner import SkillResult, run_skill
from .schema import to_input_schema

__all__ = [
    "CredentialError",
    "Skill",
    "SkillArg",
    "SkillEntry",
    "SkillResult",
    "get_skill",
    "load_registry",
    "repo_root",
    "resolve_env",
    "run_skill",
    "to_input_schema",
]

__version__ = "0.1.0"
