"""Statically verify that manifest arguments exist in each argparse script."""

from __future__ import annotations

import ast
from pathlib import Path

from .registry import Skill, load_registry, repo_root


def _literal_string(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract_arguments(script_path: Path) -> set[str]:
    """Collect long flags and positional names without importing skill code."""
    tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    arguments: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "add_argument":
            continue
        literals = [value for arg in node.args if (value := _literal_string(arg))]
        long_flags = [value for value in literals if value.startswith("--")]
        if long_flags:
            arguments.update(long_flags)
        elif literals and not literals[0].startswith("-"):
            arguments.add(literals[0])
    return arguments


def validate_skill(skill: Skill) -> dict[str, object]:
    declared = extract_arguments(skill.entry.script_path())
    missing = sorted(token for arg in skill.args if (token := arg.flag or arg.name) not in declared)
    return {"tool_name": skill.tool_name, "checked": True, "missing": missing}


def validate_manifest() -> list[dict[str, object]]:
    return [validate_skill(skill) for skill in load_registry()]


def main() -> int:
    failures = 0
    for report in validate_manifest():
        status = "FAIL" if report["missing"] else "ok"
        print(f"[{status:4}] {report['tool_name']}  missing={report['missing']}")
        failures += bool(report["missing"])
    print(f"\nrepo root: {repo_root()}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
