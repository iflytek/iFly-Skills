"""MCP v2 stdio server exposing the checked-in iFLYTEK skill scripts."""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import subprocess
from urllib.parse import quote

import anyio
import mcp.types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server

from .credentials import CANONICAL_CREDENTIALS, CredentialError
from .registry import load_registry
from .runner import SkillResult, run_skill
from .schema import to_input_schema

SERVER_NAME = "iflytek-skills"
MAX_TEXT_CHARS = 16_000
LOGGER = logging.getLogger(__name__)


def _redact(text: str) -> str:
    redacted = text
    for name in CANONICAL_CREDENTIALS:
        value = os.environ.get(name)
        if value:
            redacted = redacted.replace(value, "[redacted]")
    if len(redacted) > MAX_TEXT_CHARS:
        return redacted[:MAX_TEXT_CHARS] + "\n[output truncated]"
    return redacted


def _text(value: str) -> types.TextContent:
    return types.TextContent(type="text", text=_redact(value))


def _result_content(result: SkillResult, tool_name: str) -> list[types.ContentBlock]:
    content: list[types.ContentBlock] = []
    if result.stdout.strip():
        content.append(_text(result.stdout.strip()))
    if result.artifact_omitted_reason:
        content.append(_text(result.artifact_omitted_reason))
    if result.artifact_bytes is not None and result.artifact_name:
        mime_type = mimetypes.guess_type(result.artifact_name)[0] or "application/octet-stream"
        resource = types.BlobResourceContents(
            uri=f"artifact://{tool_name}/{quote(result.artifact_name)}",
            mime_type=mime_type,
            blob=base64.b64encode(result.artifact_bytes).decode("ascii"),
        )
        content.append(types.EmbeddedResource(type="resource", resource=resource))
    if not result.ok:
        detail = result.stderr.strip() or f"Skill exited with code {result.returncode}."
        content.append(_text(detail))
    if not content:
        content.append(_text("The skill completed without text or an artifact."))
    return content


async def handle_list_tools(
    ctx: ServerRequestContext,
    params: types.PaginatedRequestParams | None,
) -> types.ListToolsResult:
    del ctx, params
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name=skill.tool_name,
                title=skill.summary,
                description=skill.summary,
                input_schema=to_input_schema(skill),
            )
            for skill in load_registry()
        ]
    )


async def handle_call_tool(
    ctx: ServerRequestContext,
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    del ctx
    try:
        result = await anyio.to_thread.run_sync(
            run_skill,
            params.name,
            params.arguments or {},
        )
    except (CredentialError, KeyError, ValueError) as exc:
        return types.CallToolResult(content=[_text(str(exc))], is_error=True)
    except subprocess.TimeoutExpired:
        return types.CallToolResult(
            content=[_text("The skill timed out before completing.")],
            is_error=True,
        )
    except OSError:
        LOGGER.exception("Could not execute tool %s", params.name)
        return types.CallToolResult(
            content=[_text("The skill process could not be started.")],
            is_error=True,
        )

    return types.CallToolResult(
        content=_result_content(result, params.name),
        is_error=not result.ok,
    )


server = Server(
    SERVER_NAME,
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


async def _run_stdio() -> None:
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


def main() -> None:
    anyio.run(_run_stdio)


if __name__ == "__main__":
    main()
