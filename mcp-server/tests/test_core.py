"""Tests for the MCP registry, credential mapping, schemas, and runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from iflyskills_mcp import credentials, load_registry, runner, to_input_schema
from iflyskills_mcp.credentials import CredentialError, resolve_env
from iflyskills_mcp.registry import Skill, SkillArg, SkillEntry, get_skill


def test_registry_matches_current_scripts() -> None:
    skills = load_registry()
    assert len(skills) == 8
    assert len({skill.tool_name for skill in skills}) == len(skills)
    assert all(skill.entry.script_path().is_file() for skill in skills)


@pytest.mark.parametrize(
    ("profile", "prefix"),
    [("xfei", "XFEI"), ("xfyun", "XFYUN"), ("ifly", "IFLY")],
)
def test_resolve_env_maps_canonical_names(profile: str, prefix: str) -> None:
    env = resolve_env(
        profile,
        {
            "IFLYTEK_APP_ID": "app",
            "IFLYTEK_API_KEY": "key",
            "IFLYTEK_API_SECRET": "secret",
        },
    )
    assert env == {
        f"{prefix}_APP_ID": "app",
        f"{prefix}_API_KEY": "key",
        f"{prefix}_API_SECRET": "secret",
    }


def test_resolve_env_reports_names_not_values() -> None:
    with pytest.raises(CredentialError) as caught:
        resolve_env("xfei", {"IFLYTEK_APP_ID": "do-not-echo"})
    assert "IFLYTEK_API_KEY" in str(caught.value)
    assert "do-not-echo" not in str(caught.value)


def test_input_schema_hides_managed_output_and_marks_required() -> None:
    tts = get_skill("hyper_tts")
    schema = to_input_schema(tts)
    assert "output" not in schema["properties"]
    assert "text" in schema["required"]
    assert schema["properties"]["sample_rate"]["type"] == "integer"


def test_build_argv_validates_and_keeps_positionals_first() -> None:
    translate = get_skill("translate")
    argv, managed = runner.build_argv(
        translate,
        {"text": "hello", "to_lang": "en", "raw": True},
    )
    assert managed is None
    assert argv.index("hello") < argv.index("--to")
    assert argv[-1] == "--raw"

    with pytest.raises(ValueError, match="Unknown arguments"):
        runner.build_argv(translate, {"text": "hello", "output": "elsewhere"})
    with pytest.raises(ValueError, match="Missing required arguments"):
        runner.build_argv(translate, {})
    with pytest.raises(ValueError, match="must be a boolean"):
        runner.build_argv(translate, {"text": "hello", "raw": "yes"})


def test_file_arguments_are_validated_before_creating_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.tempfile,
        "mkstemp",
        lambda **kwargs: pytest.fail("temporary output created before validation"),
    )
    with pytest.raises(ValueError, match="speed must be an integer"):
        runner.build_argv(get_skill("hyper_tts"), {"text": "hello", "speed": "fast"})
    with pytest.raises(ValueError, match="managed by the MCP server"):
        runner.build_argv(
            get_skill("hyper_tts"),
            {"text": "hello", "output": "caller-owned.mp3"},
        )


def test_transcript_output_suffix_follows_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    monkeypatch.setenv(runner.ALLOWED_INPUT_DIR, str(tmp_path))
    _, managed = runner.build_argv(
        get_skill("transcribe"),
        {"file_path": str(audio), "output_format": "json"},
    )
    assert managed and managed.endswith(".json")
    Path(managed).unlink()


def test_local_file_tools_are_bounded_to_allowed_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "image.png"
    inside.write_bytes(b"image")
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"image")
    skill = get_skill("image_ocr")

    monkeypatch.delenv(runner.ALLOWED_INPUT_DIR, raising=False)
    with pytest.raises(ValueError, match=runner.ALLOWED_INPUT_DIR):
        runner.build_argv(skill, {"image_path": str(inside)})

    monkeypatch.setenv(runner.ALLOWED_INPUT_DIR, str(allowed))
    argv, _ = runner.build_argv(skill, {"image_path": str(inside)})
    assert str(inside.resolve()) in argv
    with pytest.raises(ValueError, match="must be an existing file"):
        runner.build_argv(skill, {"image_path": str(outside)})
    with pytest.raises(ValueError, match="must be a string"):
        runner.build_argv(skill, {"image_path": 42})


def _file_skill() -> Skill:
    return Skill(
        id="test-skill",
        tool_name="test_skill",
        summary="test",
        entry=SkillEntry(script="skills/test/script.py"),
        cred_profile="xfei",
        output="file",
        args=[
            SkillArg(name="text", required=True),
            SkillArg(
                name="output",
                flag="--output",
                default="output.bin",
                is_output_path=True,
            ),
        ],
    )


def test_missing_credentials_fail_before_creating_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "get_skill", lambda *args, **kwargs: _file_skill())
    monkeypatch.setattr(
        runner.tempfile,
        "mkstemp",
        lambda **kwargs: pytest.fail("temporary output created before credentials"),
    )
    for name in credentials.CANONICAL_CREDENTIALS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(CredentialError, match="IFLYTEK_APP_ID"):
        runner.run_skill("test_skill", {"text": "hello"})


def test_run_skill_scrubs_canonical_credentials_and_cleans_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = tmp_path / "script.py"
    script.write_text(
        """import json, os, pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
output.write_bytes(b'artifact')
print(json.dumps({'mapped': os.getenv('XFEI_API_KEY'), 'canonical': os.getenv('IFLYTEK_API_KEY')}))
""",
        encoding="utf-8",
    )
    artifact = tmp_path / "managed.bin"

    monkeypatch.setattr(runner, "get_skill", lambda *args, **kwargs: _file_skill())
    monkeypatch.setattr(SkillEntry, "script_path", lambda self: script)
    monkeypatch.setattr(
        runner.tempfile,
        "mkstemp",
        lambda **kwargs: (os.open(artifact, os.O_CREAT | os.O_RDWR), str(artifact)),
    )
    monkeypatch.setenv(credentials.CANONICAL_API_KEY, "ambient-key")

    result = runner.run_skill(
        "test_skill",
        {"text": "hello"},
        credentials={
            "IFLYTEK_APP_ID": "app",
            "IFLYTEK_API_KEY": "override-key",
            "IFLYTEK_API_SECRET": "secret",
        },
    )

    child_env = json.loads(result.stdout)
    assert child_env == {"mapped": "override-key", "canonical": None}
    assert result.artifact_bytes == b"artifact"
    assert result.artifact_name == "artifact.bin"
    assert not artifact.exists()


def test_run_skill_omits_oversized_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = tmp_path / "script.py"
    script.write_text(
        """import pathlib, sys
pathlib.Path(sys.argv[sys.argv.index('--output') + 1]).write_bytes(b'abc')
""",
        encoding="utf-8",
    )
    artifact = tmp_path / "managed.bin"
    monkeypatch.setattr(runner, "get_skill", lambda *args, **kwargs: _file_skill())
    monkeypatch.setattr(SkillEntry, "script_path", lambda self: script)
    monkeypatch.setattr(
        runner.tempfile,
        "mkstemp",
        lambda **kwargs: (os.open(artifact, os.O_CREAT | os.O_RDWR), str(artifact)),
    )
    monkeypatch.setenv("IFLYSKILLS_MAX_ARTIFACT_BYTES", "2")

    result = runner.run_skill(
        "test_skill",
        {"text": "hello"},
        credentials={
            "IFLYTEK_APP_ID": "app",
            "IFLYTEK_API_KEY": "key",
            "IFLYTEK_API_SECRET": "secret",
        },
    )

    assert result.artifact_bytes is None
    assert result.artifact_omitted_reason == "Artifact omitted because it is 3 bytes."
    assert not artifact.exists()
