"""Load and validate the MCP tool manifest."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PKG_DIR = Path(__file__).resolve().parent
_DEFAULT_MANIFEST = _PKG_DIR / "skills.yaml"
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ARG_TYPES = {"string", "integer", "number", "boolean", "enum"}
_CREDENTIAL_PROFILES = {"xfei", "xfyun", "ifly", "none"}
_OUTPUT_TYPES = {"stdout_text", "file", "json", "async_task"}


def repo_root() -> Path:
    """Return the root that contains the checked-in ``skills`` directory.

    Source checkouts keep this package under ``mcp-server/`` while staged MCPB
    bundles place it at their root. ``IFLY_SKILLS_ROOT`` is the explicit escape
    hatch used by Docker and MCPB hosts.
    """
    override = os.environ.get("IFLY_SKILLS_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / "skills").is_dir():
            raise RuntimeError(f"IFLY_SKILLS_ROOT has no skills directory: {root}")
        return root

    for candidate in (_PKG_DIR.parent, _PKG_DIR.parent.parent):
        if (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError("Could not locate the iFly-Skills repository root")


def _script_path(relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Skill script must be a repository-relative path: {relative}")
    root = repo_root()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:  # pragma: no cover - resolve-time defense
        raise ValueError(f"Skill script escapes the repository root: {relative}") from exc
    if not path.is_file():
        raise ValueError(f"Skill script does not exist: {relative}")
    return path


@dataclass(frozen=True)
class SkillArg:
    name: str
    flag: str | None = None
    type: str = "string"
    required: bool = False
    default: Any = None
    enum: list[Any] | None = None
    description: str = ""
    is_input_path: bool = False
    is_output_path: bool = False

    @property
    def is_positional(self) -> bool:
        return self.flag is None


@dataclass(frozen=True)
class SkillEntry:
    script: str
    subcommand: str | None = None

    def script_path(self) -> Path:
        return _script_path(self.script)


@dataclass(frozen=True)
class Skill:
    id: str
    tool_name: str
    summary: str
    entry: SkillEntry
    cred_profile: str
    output: str
    advanced: bool = False
    args: list[SkillArg] = field(default_factory=list)

    @property
    def output_path_arg(self) -> SkillArg | None:
        return next((arg for arg in self.args if arg.is_output_path), None)


def _parse_skill(raw: Any) -> Skill:
    if not isinstance(raw, dict):
        raise ValueError("Each skills.yaml entry must be an object")
    entry_raw = raw.get("entry")
    if not isinstance(entry_raw, dict) or not isinstance(entry_raw.get("script"), str):
        raise ValueError("Each skill requires entry.script")

    raw_args = raw.get("args", [])
    if not isinstance(raw_args, list):
        raise ValueError(f"args must be a list for {raw.get('tool_name', '<unknown>')}")
    args = [
        SkillArg(
            name=arg["name"],
            flag=arg.get("flag"),
            type=arg.get("type", "string"),
            required=bool(arg.get("required", False)),
            default=arg.get("default"),
            enum=arg.get("enum"),
            description=arg.get("description", ""),
            is_input_path=bool(arg.get("is_input_path", False)),
            is_output_path=bool(arg.get("is_output_path", False)),
        )
        for arg in raw_args
        if isinstance(arg, dict) and isinstance(arg.get("name"), str)
    ]
    if len(args) != len(raw_args):
        raise ValueError(f"Every argument needs a name for {raw.get('tool_name', '<unknown>')}")

    return Skill(
        id=raw["id"],
        tool_name=raw["tool_name"],
        summary=raw["summary"],
        entry=SkillEntry(
            script=entry_raw["script"],
            subcommand=entry_raw.get("subcommand"),
        ),
        cred_profile=raw.get("cred_profile", "none"),
        output=raw.get("output", "stdout_text"),
        advanced=bool(raw.get("advanced", False)),
        args=args,
    )


def _validate_skill(skill: Skill) -> None:
    if not skill.id or not _TOOL_NAME.fullmatch(skill.tool_name):
        raise ValueError(f"Invalid tool identity: {skill.tool_name!r}")
    if not skill.summary.strip():
        raise ValueError(f"Missing summary for {skill.tool_name}")
    if skill.cred_profile not in _CREDENTIAL_PROFILES:
        raise ValueError(f"Unknown credential profile for {skill.tool_name}: {skill.cred_profile}")
    if skill.output not in _OUTPUT_TYPES:
        raise ValueError(f"Unknown output type for {skill.tool_name}: {skill.output}")
    if sum(arg.is_output_path for arg in skill.args) > 1:
        raise ValueError(f"Only one managed output path is allowed for {skill.tool_name}")

    seen_args: set[str] = set()
    for arg in skill.args:
        if arg.name in seen_args:
            raise ValueError(f"Duplicate argument {arg.name!r} for {skill.tool_name}")
        seen_args.add(arg.name)
        if arg.type not in _ARG_TYPES:
            raise ValueError(f"Unknown argument type {arg.type!r} for {skill.tool_name}.{arg.name}")
        if arg.flag is not None and not arg.flag.startswith("--"):
            raise ValueError(f"Flags must use their long form for {skill.tool_name}.{arg.name}")
        if arg.is_input_path and arg.is_output_path:
            raise ValueError(
                f"An argument cannot be both input and output: {skill.tool_name}.{arg.name}"
            )
        if arg.enum is not None and not arg.enum:
            raise ValueError(f"Empty enum for {skill.tool_name}.{arg.name}")
    skill.entry.script_path()


def load_registry(manifest: os.PathLike[str] | None = None) -> list[Skill]:
    """Parse and validate ``skills.yaml`` without executing skill code."""
    path = Path(manifest) if manifest else _DEFAULT_MANIFEST
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise ValueError(f"{path} must contain a skills list")

    skills = [_parse_skill(item) for item in data["skills"]]
    seen_tools: set[str] = set()
    for skill in skills:
        if skill.tool_name in seen_tools:
            raise ValueError(f"Duplicate tool_name in manifest: {skill.tool_name}")
        seen_tools.add(skill.tool_name)
        _validate_skill(skill)
    return skills


def get_skill(tool_name: str, manifest: os.PathLike[str] | None = None) -> Skill:
    for skill in load_registry(manifest):
        if skill.tool_name == tool_name:
            return skill
    raise KeyError(f"Unknown skill tool_name: {tool_name}")
