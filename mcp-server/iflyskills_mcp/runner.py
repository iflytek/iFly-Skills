"""Execute checked-in iFLYTEK skill scripts without a shell."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .credentials import CANONICAL_CREDENTIALS, resolve_env
from .registry import Skill, SkillArg, get_skill

DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_MAX_ARTIFACT_BYTES = 20 * 1024 * 1024
ALLOWED_INPUT_DIR = "IFLYSKILLS_ALLOWED_DIR"


@dataclass(frozen=True)
class SkillResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    artifact_name: str | None = None
    artifact_bytes: bytes | None = None
    artifact_omitted_reason: str | None = None


def _render_value(arg: SkillArg, value: Any) -> list[str]:
    if arg.type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{arg.name} must be a boolean")
        return [arg.flag] if value else []
    if arg.type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{arg.name} must be an integer")
    if arg.type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise ValueError(f"{arg.name} must be a number")
    if arg.type in {"string", "enum"} and not isinstance(value, str):
        if not (arg.enum and value in arg.enum):
            raise ValueError(f"{arg.name} must be a string")
    if arg.enum is not None and value not in arg.enum:
        raise ValueError(f"{arg.name} must be one of {arg.enum}")
    if arg.is_positional:
        return [str(value)]
    if arg.flag is None:  # pragma: no cover - registry invariant
        raise ValueError(f"Missing flag for {arg.name}")
    return [arg.flag, str(value)]


def _suffix_for(arg: SkillArg, provided: Mapping[str, Any]) -> str:
    output_format = provided.get("format") or provided.get("output_format")
    if isinstance(output_format, str) and output_format and "," not in output_format:
        return f".{output_format}"
    if isinstance(arg.default, str) and "." in arg.default:
        return arg.default[arg.default.rfind(".") :]
    return ".bin"


def _validated_input_path(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    configured_root = os.environ.get(ALLOWED_INPUT_DIR)
    if not configured_root:
        raise ValueError(f"{ALLOWED_INPUT_DIR} is required for local-file tools")
    try:
        allowed_root = Path(configured_root).expanduser().resolve(strict=True)
        candidate = Path(value).expanduser().resolve(strict=True)
        candidate.relative_to(allowed_root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ValueError(f"{name} must be an existing file inside {ALLOWED_INPUT_DIR}") from exc
    if not allowed_root.is_dir() or not candidate.is_file():
        raise ValueError(f"{name} must be an existing file inside {ALLOWED_INPUT_DIR}")
    return str(candidate)


def build_argv(skill: Skill, args: Mapping[str, Any]) -> tuple[list[str], str | None]:
    """Build an argument vector and create a server-owned output path if needed."""
    known = {arg.name for arg in skill.args}
    unknown = sorted(set(args) - known)
    if unknown:
        raise ValueError("Unknown arguments: " + ", ".join(unknown))

    missing = [
        arg.name
        for arg in skill.args
        if arg.required and not arg.is_output_path and args.get(arg.name) is None
    ]
    if missing:
        raise ValueError("Missing required arguments: " + ", ".join(missing))

    rendered_arguments: dict[str, list[str]] = {}
    for arg in skill.args:
        if arg.is_output_path:
            if arg.name in args:
                raise ValueError(f"{arg.name} is managed by the MCP server")
            continue
        value = args.get(arg.name)
        if value is not None:
            if arg.is_input_path:
                value = _validated_input_path(arg.name, value)
            rendered_arguments[arg.name] = _render_value(arg, value)

    argv = [sys.executable, str(skill.entry.script_path())]
    if skill.entry.subcommand:
        argv.append(skill.entry.subcommand)

    managed_output: str | None = None
    positionals: list[str] = []
    options: list[str] = []
    for arg in skill.args:
        if arg.is_output_path:
            suffix = _suffix_for(arg, args)
            descriptor, managed_output = tempfile.mkstemp(
                suffix=suffix,
                prefix="iflyskills_mcp_",
            )
            os.close(descriptor)
            options.extend(_render_value(arg, managed_output))
            continue

        tokens = rendered_arguments.get(arg.name)
        if tokens is None:
            continue
        (positionals if arg.is_positional else options).extend(tokens)

    argv.extend(positionals)
    argv.extend(options)
    return argv, managed_output


def _max_artifact_bytes() -> int:
    raw = os.environ.get("IFLYSKILLS_MAX_ARTIFACT_BYTES")
    if raw is None:
        return DEFAULT_MAX_ARTIFACT_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("IFLYSKILLS_MAX_ARTIFACT_BYTES must be an integer") from exc
    if value < 1:
        raise ValueError("IFLYSKILLS_MAX_ARTIFACT_BYTES must be positive")
    return value


def run_skill(
    tool_name: str,
    args: Mapping[str, Any],
    credentials: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    manifest: os.PathLike[str] | None = None,
) -> SkillResult:
    """Run one manifest tool and return bounded text and optional artifact bytes."""
    skill = get_skill(tool_name, manifest)
    child_credentials = resolve_env(skill.cred_profile, credentials)
    argv, managed_output = build_argv(skill, args)

    env = dict(os.environ)
    for canonical_name in CANONICAL_CREDENTIALS:
        env.pop(canonical_name, None)
    env.update(child_credentials)
    env.setdefault("PYTHONIOENCODING", "utf-8")

    try:
        with tempfile.TemporaryDirectory(prefix="iflyskills_mcp_work_") as work_dir:
            process = subprocess.run(
                argv,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )

        artifact_name: str | None = None
        artifact_bytes: bytes | None = None
        artifact_omitted_reason: str | None = None
        if process.returncode == 0 and skill.output == "file" and managed_output:
            artifact_path = Path(managed_output)
            size = artifact_path.stat().st_size if artifact_path.exists() else 0
            if size == 0:
                artifact_omitted_reason = "The skill did not produce an artifact."
            elif size > _max_artifact_bytes():
                artifact_omitted_reason = f"Artifact omitted because it is {size} bytes."
            else:
                artifact_bytes = artifact_path.read_bytes()
                artifact_name = f"artifact{artifact_path.suffix or '.bin'}"

        return SkillResult(
            ok=process.returncode == 0,
            returncode=process.returncode,
            stdout=process.stdout or "",
            stderr=process.stderr or "",
            artifact_name=artifact_name,
            artifact_bytes=artifact_bytes,
            artifact_omitted_reason=artifact_omitted_reason,
        )
    finally:
        if managed_output:
            Path(managed_output).unlink(missing_ok=True)
