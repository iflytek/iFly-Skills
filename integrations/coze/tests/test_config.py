"""Runtime configuration: explicit sites, immutable scope and no credential fallback."""

import os
from pathlib import Path

import pytest

from app.config import ConfigurationError, load_settings, read_config


def runtime_values():
    return {
        "COZE_ENABLED_SITES": "cn,global",
        "COZE_CN_WORKSPACE_ID": "cn-space",
        "COZE_CN_BACKEND_API_KEY": "cn-" + "a" * 40,
        "COZE_CN_ALLOWED_SKILLS": "iflytek-translate,iflytek-hyper-tts",
        "COZE_GLOBAL_WORKSPACE_ID": "global-space",
        "COZE_GLOBAL_BACKEND_API_KEY": "global-" + "b" * 40,
        "COZE_GLOBAL_ALLOWED_SKILLS": "iflytek-image-understanding",
    }


def test_runtime_does_not_require_platform_token_domain_or_upstream_credentials():
    settings = load_settings(environ=runtime_values())
    assert [grant.principal.site for grant in settings.grants] == ["cn", "global"]
    assert settings.grants[0].principal.workspace_id == "cn-space"
    assert settings.grants[1].principal.allowed_skills == frozenset({"iflytek-image-understanding"})
    assert "cn-space" not in repr(settings)
    assert "a" * 40 not in repr(settings)


@pytest.mark.parametrize("key,value", [
    ("COZE_ENABLED_SITES", ""), ("COZE_ENABLED_SITES", "cn,cn"),
    ("COZE_ENABLED_SITES", "other"), ("COZE_GLOBAL_WORKSPACE_ID", ""),
    ("COZE_GLOBAL_BACKEND_API_KEY", ""), ("COZE_CN_BACKEND_API_KEY", "short-secret"),
    ("COZE_CN_BACKEND_API_KEY", "密" * 40), ("COZE_CN_BACKEND_API_KEY", "x" * 40 + "\n"),
    ("COZE_CN_ALLOWED_SKILLS", ""), ("COZE_CN_ALLOWED_SKILLS", "*"),
    ("COZE_CN_ALLOWED_SKILLS", "not-a-skill"),
])
def test_invalid_runtime_configuration_fails_closed(key, value):
    values = runtime_values()
    values[key] = value
    with pytest.raises(ConfigurationError) as error:
        load_settings(environ=values)
    if len(value) > 20:
        assert value not in str(error.value)


def test_disabled_site_neither_requires_configuration_nor_creates_a_grant():
    values = {key: value for key, value in runtime_values().items() if not key.startswith("COZE_GLOBAL_")}
    values["COZE_ENABLED_SITES"] = "cn"
    assert len(load_settings(environ=values).grants) == 1


def test_duplicate_service_keys_and_reused_platform_tokens_are_rejected():
    values = runtime_values()
    values["COZE_GLOBAL_BACKEND_API_KEY"] = values["COZE_CN_BACKEND_API_KEY"]
    with pytest.raises(ConfigurationError, match="separate"):
        load_settings(environ=values)
    values = runtime_values()
    values["COZE_GLOBAL_API_TOKEN"] = values["COZE_CN_BACKEND_API_KEY"]
    with pytest.raises(ConfigurationError, match="platform token"):
        load_settings(environ=values)


def test_file_is_explicit_and_process_values_override_without_mutating_environment(tmp_path, monkeypatch):
    values = runtime_values()
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError):
        load_settings(environ={})  # Never automatically read a cwd .env.
    environment = {"COZE_ENV_FILE": str(path), "COZE_CN_WORKSPACE_ID": "overridden-space"}
    before = dict(os.environ)
    settings = load_settings(environ=environment)
    assert settings.grants[0].principal.workspace_id == "overridden-space"
    assert dict(os.environ) == before
    environment["COZE_CN_BACKEND_API_KEY"] = ""
    with pytest.raises(ConfigurationError):
        load_settings(environ=environment)
    with pytest.raises(ConfigurationError, match="Cannot read"):
        load_settings(env_file=tmp_path / "absent", environ={})


@pytest.mark.parametrize("text", [
    "UNKNOWN_PRIVATE_VALUE=secret", "COZE_ENABLED_SITES", "COZE_CN_API_TOKEN='unclosed-secret",
])
def test_invalid_file_errors_do_not_echo_values(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError) as error:
        read_config(path)
    assert "secret" not in str(error.value)
    assert "UNKNOWN_PRIVATE_VALUE" not in str(error.value)


def test_file_values_are_literal_and_not_shell_or_environment_expanded(tmp_path):
    path = tmp_path / ".env"
    path.write_text('COZE_CN_WORKSPACE_ID="${SECRET}#literal"\n', encoding="utf-8")
    assert read_config(path)["COZE_CN_WORKSPACE_ID"] == "${SECRET}#literal"


def test_example_and_preparation_reader_share_the_runtime_config_contract():
    example = Path(__file__).parents[1] / ".env.example"
    values = read_config(example)
    assert values["COZE_CN_BACKEND_API_KEY"] == values["COZE_GLOBAL_API_TOKEN"] == ""
    with pytest.raises(ConfigurationError):
        load_settings(env_file=example, environ={})
