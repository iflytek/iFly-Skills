"""Request authentication, trace IDs and logs that exclude payloads and credentials."""

import hmac
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Security
from fastapi.security import APIKeyHeader
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Principal, Settings
from .errors import ErrorCode, ServiceError, error_response


# Inherit Uvicorn's handlers and level without changing global logging settings.
LOGGER = logging.getLogger("uvicorn.error.coze")
API_KEY = APIKeyHeader(name="X-API-Key", scheme_name="ServiceApiKey", auto_error=False)


def require_skill(skill_id: str):
    def authorize(request: Request, _key: str | None = Security(API_KEY)) -> Principal:
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise ServiceError(ErrorCode.AUTHENTICATION_FAILED)
        if skill_id not in principal.allowed_skills:
            raise ServiceError(ErrorCode.FORBIDDEN)
        return principal

    return authorize


class RequestMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state.update(trace_id=uuid4().hex, principal=None, error_code="")
        started_at = perf_counter()
        response_started = False
        status = 500

        async def traced_send(message: Message):
            nonlocal response_started, status
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-trace-id"]
                message = {**message, "headers": headers + [(b"x-trace-id", state["trace_id"].encode("ascii"))]}
            await send(message)

        try:
            path = scope["path"]
            if path == "/v1/skills" or path.startswith("/v1/skills/"):
                keys = [value for key, value in scope["headers"] if key.lower() == b"x-api-key"]
                if len(keys) == 1 and len(keys[0]) <= 256:
                    for grant in self.settings.grants:
                        if hmac.compare_digest(keys[0], grant.api_key.encode("ascii")):
                            state["principal"] = grant.principal
                if state["principal"] is None:
                    await error_response(scope, ErrorCode.AUTHENTICATION_FAILED)(scope, receive, traced_send)
                    return
            await self.app(scope, receive, traced_send)
        except Exception:
            state["error_code"] = ErrorCode.INTERNAL_ERROR.value
            if response_started:
                # Do not re-raise an exception that may contain upstream secrets.
                raise RuntimeError("Response interrupted; consult the request trace ID") from None
            await error_response(scope, ErrorCode.INTERNAL_ERROR)(scope, receive, traced_send)
        finally:
            route = scope.get("route")
            operation = getattr(route, "operation_id", None) or "management_or_unmatched"
            LOGGER.info("trace_id=%s operation=%s status=%s error=%s duration_ms=%.2f",
                        state["trace_id"], operation, status, state["error_code"], (perf_counter() - started_at) * 1000)
