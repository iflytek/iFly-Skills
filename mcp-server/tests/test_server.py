"""Tests for the MCP v2 protocol handlers."""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import urlopen

import anyio
import mcp.types as types
import pytest
import uvicorn
from mcp import Client
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

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


@contextmanager
def _live_sse_server(*, bearer_token: str | None = None):
    app = server.create_sse_app(bearer_token=bearer_token)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    uvicorn_server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="off"))
    thread = threading.Thread(
        target=uvicorn_server.run,
        kwargs={"sockets": [listener]},
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 5
    while not uvicorn_server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not uvicorn_server.started:
        pytest.fail("SSE test server did not start")
    try:
        yield port
    finally:
        uvicorn_server.should_exit = True
        thread.join(timeout=5)
        listener.close()


def test_sse_requires_bearer_and_completes_official_client_handshake() -> None:
    async def exercise(port: int) -> set[str]:
        headers = {"Authorization": "Bearer test-token"}
        async with sse_client(
            f"http://127.0.0.1:{port}/sse",
            headers=headers,
            sse_read_timeout=5,
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                listed = await session.list_tools()
                return {tool.name for tool in listed.tools}

    with _live_sse_server(bearer_token="test-token") as port:
        with pytest.raises(HTTPError) as denied:
            urlopen(f"http://127.0.0.1:{port}/sse", timeout=2)
        assert denied.value.code == 401
        assert "translate" in anyio.run(exercise, port)


def test_non_loopback_sse_requires_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(server.SSE_BEARER_TOKEN_ENV, raising=False)
    with pytest.raises(SystemExit):
        server.main(["--transport", "sse", "--host", "0.0.0.0"])
    assert server.SSE_BEARER_TOKEN_ENV in capsys.readouterr().err


@pytest.mark.parametrize("path", ["", "/", "https://example.com/sse", "/sse?debug=1"])
def test_sse_rejects_invalid_route_paths(path: str) -> None:
    with pytest.raises(ValueError, match="relative URL paths"):
        server.create_sse_app(sse_path=path)


def test_sse_requires_distinct_connection_and_message_routes() -> None:
    with pytest.raises(ValueError, match="must be different"):
        server.create_sse_app(sse_path="/mcp", message_path="/mcp/")
