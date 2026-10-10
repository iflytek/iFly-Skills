"""Register only implemented endpoints from the fixed Skill inventory."""

from collections.abc import Callable

from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

from .catalog import Tool
from .errors import ERRORS, ErrorEnvelope
from .security import require_skill


def register_tool(app: FastAPI, skill_id: str, action: str, endpoint: Callable, *,
                  response_model: type[BaseModel], status_code: int = 200) -> None:
    tool = Tool(skill_id, action)
    if not isinstance(response_model, type) or not issubclass(response_model, BaseModel):
        raise ValueError("A concrete response model is required")
    if status_code not in (200, 202) or (tool.method == "GET" and status_code != 200):
        raise ValueError("Queries return 200; submissions return 200 or 202")
    if any(getattr(route, "operation_id", None) == tool.operation_id or getattr(route, "path", None) == tool.path
           for route in app.routes):
        raise ValueError("The tool route is already registered")
    definition = dict(
        path=tool.path, endpoint=endpoint, methods=[tool.method], name=tool.operation_id,
        operation_id=tool.operation_id, tags=[skill_id], response_model=response_model,
        status_code=status_code, dependencies=[Depends(require_skill(skill_id))],
        responses={spec.status: {"model": ErrorEnvelope} for spec in ERRORS.values()},
    )
    # Validate before attaching so a rejected GET body cannot leave a live route.
    route = APIRoute(**definition)
    if tool.method == "GET" and route.body_field is not None:
        raise ValueError("GET tools must use query parameters, not a request body")
    app.add_api_route(**definition)
    app.openapi_schema = None
