"""Render manifest arguments as MCP JSON input schemas."""

from __future__ import annotations

from typing import Any

from .registry import Skill, SkillArg

_JSON_TYPES = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "enum": "string",
}


def _property_for(arg: SkillArg) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": _JSON_TYPES[arg.type]}
    if arg.enum is not None:
        prop["enum"] = arg.enum
        if all(isinstance(value, bool) for value in arg.enum):
            prop["type"] = "boolean"
        elif all(isinstance(value, int) and not isinstance(value, bool) for value in arg.enum):
            prop["type"] = "integer"
        elif all(
            isinstance(value, (int, float)) and not isinstance(value, bool) for value in arg.enum
        ):
            prop["type"] = "number"
    if arg.description:
        prop["description"] = arg.description
    if arg.default is not None:
        prop["default"] = arg.default
    return prop


def to_input_schema(skill: Skill) -> dict[str, Any]:
    """Return the exact input schema advertised by ``tools/list``."""
    public_args = [arg for arg in skill.args if not arg.is_output_path]
    properties = {arg.name: _property_for(arg) for arg in public_args}
    required = [arg.name for arg in public_args if arg.required]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema
