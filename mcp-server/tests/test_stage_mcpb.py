"""Tests for deterministic, non-destructive MCPB source staging."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage_mcpb.py"
SPEC = importlib.util.spec_from_file_location("stage_mcpb", SCRIPT)
assert SPEC and SPEC.loader
stage_mcpb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_mcpb)


def test_stage_contains_runtime_and_sensitive_credential_contract(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    stage_mcpb.stage(output)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "0.4"
    assert set(manifest["user_config"]) == {
        "allowed_directory",
        "iflytek_app_id",
        "iflytek_api_key",
        "iflytek_api_secret",
    }
    assert manifest["user_config"]["allowed_directory"]["type"] == "directory"
    assert all(
        manifest["user_config"][name]["sensitive"]
        for name in ("iflytek_app_id", "iflytek_api_key", "iflytek_api_secret")
    )
    assert (output / "iflyskills_mcp" / "server.py").is_file()
    assert (output / "uv.lock").is_file()
    assert (output / "skills" / "iflytek-translate" / "scripts" / "translate.py").is_file()
    assert not (output / "tests").exists()
    assert not list(output.rglob("__pycache__"))
    assert not list(output.rglob("*.pyc"))


def test_stage_refuses_to_replace_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to replace"):
        stage_mcpb.stage(output)
    assert marker.read_text(encoding="utf-8") == "keep"
