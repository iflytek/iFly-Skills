"""Uvicorn factory: uvicorn app.main:create_app --factory --no-access-log."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from .config import Settings, load_settings
from .errors import ERRORS, ErrorCode, ServiceError, error_response
from .security import RequestMiddleware


class Health(BaseModel):
    status: str


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings if settings is not None else load_settings()
    app = FastAPI(title="iFly-Skills Coze backend", version="0.1.0", debug=False,
                  openapi_url=None, docs_url=None, redoc_url=None, redirect_slashes=False)
    app.add_middleware(RequestMiddleware, settings=configured)

    @app.get("/healthz", response_model=Health, include_in_schema=False)
    async def health() -> Health:
        return Health(status="ok")

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return error_response(request.scope, exc.code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError):
        return error_response(request.scope, ErrorCode.INVALID_REQUEST)

    @app.exception_handler(TimeoutError)
    async def timeout_error(request: Request, _exc: TimeoutError):
        return error_response(request.scope, ErrorCode.TIMEOUT)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = {
            400: ErrorCode.INVALID_REQUEST, 401: ErrorCode.AUTHENTICATION_FAILED,
            403: ErrorCode.FORBIDDEN, 404: ErrorCode.NOT_FOUND, 405: ErrorCode.METHOD_NOT_ALLOWED,
            409: ErrorCode.CONFLICT, 422: ErrorCode.INVALID_REQUEST, 429: ErrorCode.RATE_LIMITED,
            502: ErrorCode.UPSTREAM_ERROR, 503: ErrorCode.DEPENDENCY_UNAVAILABLE, 504: ErrorCode.TIMEOUT,
        }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        response = error_response(request.scope, code)
        if ERRORS[code].status == 405 and exc.headers:
            methods = {method.strip() for method in exc.headers.get("Allow", "").split(",")}
            if methods and methods <= {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                response.headers["Allow"] = ", ".join(sorted(methods))
        return response

    return app
