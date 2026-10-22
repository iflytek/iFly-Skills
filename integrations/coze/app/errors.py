"""Stable public error categories; raw upstream/validation exceptions stay private."""

from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.types import Scope


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_PERMISSION_DENIED = "UPSTREAM_PERMISSION_DENIED"
    UPSTREAM_QUOTA_EXCEEDED = "UPSTREAM_QUOTA_EXCEEDED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    UPSTREAM_PROTOCOL_ERROR = "UPSTREAM_PROTOCOL_ERROR"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorSpec(NamedTuple):
    status: int
    message: str
    retryable: bool = False


ERRORS = {
    ErrorCode.INVALID_REQUEST: ErrorSpec(422, "Request parameters are invalid."),
    ErrorCode.AUTHENTICATION_FAILED: ErrorSpec(401, "A valid service API key is required."),
    ErrorCode.FORBIDDEN: ErrorSpec(403, "This service key is not authorized for the requested skill."),
    ErrorCode.NOT_FOUND: ErrorSpec(404, "Resource not found."),
    ErrorCode.METHOD_NOT_ALLOWED: ErrorSpec(405, "HTTP method not allowed."),
    ErrorCode.CONFLICT: ErrorSpec(409, "Request conflicts with an existing operation or task state."),
    ErrorCode.RATE_LIMITED: ErrorSpec(429, "Service rate limit reached.", True),
    ErrorCode.UPSTREAM_PERMISSION_DENIED: ErrorSpec(502, "The upstream service has not granted this capability."),
    ErrorCode.UPSTREAM_QUOTA_EXCEEDED: ErrorSpec(502, "The upstream service quota is insufficient."),
    ErrorCode.UPSTREAM_ERROR: ErrorSpec(502, "The upstream service failed."),
    ErrorCode.UPSTREAM_PROTOCOL_ERROR: ErrorSpec(502, "The upstream service returned an invalid or incomplete result."),
    ErrorCode.DEPENDENCY_UNAVAILABLE: ErrorSpec(503, "A required service dependency is not configured or available."),
    ErrorCode.TIMEOUT: ErrorSpec(504, "The operation timed out; check task state before resubmitting."),
    ErrorCode.INTERNAL_ERROR: ErrorSpec(500, "An internal service error occurred."),
}


class ServiceError(Exception):
    def __init__(self, code: ErrorCode):
        self.code = ErrorCode(code)
        super().__init__(self.code.value)


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    trace_id: str


def error_response(scope: Scope, code: ErrorCode) -> JSONResponse:
    spec = ERRORS[code]
    scope["state"]["error_code"] = code.value
    body = ErrorEnvelope(
        error=ErrorDetail(code=code, message=spec.message, retryable=spec.retryable),
        trace_id=scope["state"]["trace_id"],
    )
    return JSONResponse(status_code=spec.status, content=body.model_dump(mode="json"))
