"""MCP v2 stdio and SSE server exposing checked-in iFLYTEK skill scripts."""

from __future__ import annotations

import argparse
import base64
import logging
import mimetypes
import os
import secrets
import subprocess
from collections.abc import Sequence
from urllib.parse import quote

import anyio
import mcp.types as types
import uvicorn
from mcp.server import Server, ServerRequestContext
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .credentials import CANONICAL_CREDENTIALS, CredentialError
from .registry import load_registry
from .runner import SkillResult, run_skill
from .schema import to_input_schema

SERVER_NAME = "iflytek-skills"
MAX_TEXT_CHARS = 16_000
SSE_BEARER_TOKEN_ENV = "IFLYSKILLS_MCP_BEARER_TOKEN"
DEFAULT_SSE_HOST = "127.0.0.1"
DEFAULT_SSE_PORT = 8000
DEFAULT_SSE_PATH = "/sse"
DEFAULT_MESSAGE_PATH = "/messages/"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
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


class BearerTokenMiddleware:
    """Protect both sides of an SSE session with one configured bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            authorization = Headers(scope=scope).get("authorization", "")
            scheme, separator, supplied = authorization.partition(" ")
            authenticated = (
                bool(separator)
                and scheme.lower() == "bearer"
                and secrets.compare_digest(supplied, self._token)
            )
            if not authenticated:
                response = Response(
                    "Unauthorized",
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


def _normalise_route(value: str, *, trailing_slash: bool) -> str:
    route = value.strip("/")
    if not route or "://" in value or "?" in value or "#" in value:
        raise ValueError("SSE routes must be non-empty relative URL paths")
    normalised = "/" + route
    return normalised + "/" if trailing_slash else normalised


def _default_allowed_hosts(bind_host: str) -> list[str]:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if bind_host not in {"0.0.0.0", "::"}:
        hosts.extend((bind_host, f"{bind_host}:*"))
    return list(dict.fromkeys(hosts))


def _default_allowed_origins(bind_host: str) -> list[str]:
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if bind_host not in {"0.0.0.0", "::"}:
        origins.extend((f"http://{bind_host}:*", f"https://{bind_host}:*"))
    return list(dict.fromkeys(origins))


def create_sse_app(
    *,
    bind_host: str = DEFAULT_SSE_HOST,
    sse_path: str = DEFAULT_SSE_PATH,
    message_path: str = DEFAULT_MESSAGE_PATH,
    allowed_hosts: Sequence[str] = (),
    allowed_origins: Sequence[str] = (),
    bearer_token: str | None = None,
) -> Starlette:
    """Create the legacy SSE ASGI transport with rebinding and optional auth guards."""
    sse_route = _normalise_route(sse_path, trailing_slash=False)
    message_route = _normalise_route(message_path, trailing_slash=True)
    if sse_route.rstrip("/") == message_route.rstrip("/"):
        raise ValueError("SSE and message routes must be different")

    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys([*_default_allowed_hosts(bind_host), *allowed_hosts])),
        allowed_origins=list(
            dict.fromkeys([*_default_allowed_origins(bind_host), *allowed_origins])
        ),
    )
    transport = SseServerTransport(message_route, security_settings=security)

    async def handle_sse(request: Request) -> Response:
        try:
            async with transport.connect_sse(
                request.scope,
                request.receive,
                request._send,
            ) as streams:
                await server.run(
                    streams[0],
                    streams[1],
                    server.create_initialization_options(),
                )
        except ValueError as exc:
            LOGGER.debug("Rejected SSE connection: %s", exc)
        return Response()

    middleware = [Middleware(BearerTokenMiddleware, token=bearer_token)] if bearer_token else []
    return Starlette(
        routes=[
            Route(sse_route, endpoint=handle_sse, methods=["GET"]),
            Mount(message_route, app=transport.handle_post_message),
        ],
        middleware=middleware,
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "sse"), default="stdio")
    parser.add_argument("--host", default=DEFAULT_SSE_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_SSE_PORT)
    parser.add_argument("--sse-path", default=DEFAULT_SSE_PATH)
    parser.add_argument("--message-path", default=DEFAULT_MESSAGE_PATH)
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--allow-origin", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    if args.transport == "stdio":
        anyio.run(_run_stdio)
        return

    bearer_token = os.environ.get(SSE_BEARER_TOKEN_ENV)
    if args.host not in _LOOPBACK_HOSTS and not bearer_token:
        parser.error(f"{SSE_BEARER_TOKEN_ENV} is required when SSE listens on a non-loopback host")

    app = create_sse_app(
        bind_host=args.host,
        sse_path=args.sse_path,
        message_path=args.message_path,
        allowed_hosts=args.allow_host,
        allowed_origins=args.allow_origin,
        bearer_token=bearer_token,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
