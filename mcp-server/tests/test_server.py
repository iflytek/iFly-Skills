"""Tests for the MCP v2 protocol handlers."""

from __future__ import annotations

import anyio
import mcp.types as types
import pytest
from mcp import Client

from iflyskills_mcp import server
from iflyskills_mcp.credentials import CredentialError
from iflyskills_mcp.runner import SkillResult


def test_official_client_completes_handshake_and_lists_tools() -> None:
    async def exercise() -> set[str]:
        async with Client(server.server) as client:
            listed = await client.list_tools()
            return {tool.name for tool in listed.tools}

    assert "translate" in anyio.run(exercise)


def test_list_tools_uses_manifest_schema() -> None:
    result = anyio.run(server.handle_list_tools, None, None)
    by_name = {tool.name: tool for tool in result.tools}
    assert set(by_name) == {
        "hyper_tts",
        "image_ocr",
        "image_understanding",
        "ocr_invoice",
        "pdf_ocr",
        "proofread",
        "transcribe",
        "translate",
    }
    assert by_name["translate"].input_schema["required"] == ["text"]


def test_call_tool_returns_redacted_text_and_embedded_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IFLYTEK_API_SECRET", "super-secret")
    monkeypatch.setattr(
        server,
        "run_skill",
        lambda *args: SkillResult(
            ok=True,
            returncode=0,
            stdout="created with super-secret",
            stderr="",
            artifact_name="artifact.mp3",
            artifact_bytes=b"audio",
        ),
    )
    params = types.CallToolRequestParams(name="hyper_tts", arguments={"text": "hi"})
    result = anyio.run(server.handle_call_tool, None, params)

    assert result.is_error is False
    assert isinstance(result.content[0], types.TextContent)
    assert result.content[0].text == "created with [redacted]"
    assert isinstance(result.content[1], types.EmbeddedResource)
    assert str(result.content[1].resource.uri).startswith("artifact://hyper_tts/")
    assert "tmp" not in str(result.content[1].resource.uri)


def test_call_tool_returns_protocol_error_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object) -> SkillResult:
        raise CredentialError("Missing required credentials: IFLYTEK_API_KEY")

    monkeypatch.setattr(server, "run_skill", fail)
    params = types.CallToolRequestParams(name="translate", arguments={"text": "hi"})
    result = anyio.run(server.handle_call_tool, None, params)

    assert result.is_error is True
    assert isinstance(result.content[0], types.TextContent)
    assert "IFLYTEK_API_KEY" in result.content[0].text
