"""HTTP boundary tests use private test endpoints; production registers no fake tools."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import re

from fastapi import Depends, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field
import pytest

from app.catalog import SKILL_TOOLS, Tool
from app.config import Principal, Settings, SiteGrant
from app.errors import ErrorCode, ServiceError
from app.main import create_app
from app.routing import register_tool
from app.security import LOGGER, require_skill


CN_KEY = "cn-" + "a" * 40
GLOBAL_KEY = "global-" + "b" * 40
SKILL = "iflytek-translate"
PATH = "/v1/skills/iflytek-translate/translate"


@pytest.fixture
def settings():
    return Settings((
        SiteGrant(Principal("cn", "cn-private-space", frozenset({SKILL, "iflytek-hyper-tts"})), CN_KEY),
        SiteGrant(Principal("global", "global-private-space", frozenset({SKILL})), GLOBAL_KEY),
    ))


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=32)


class EchoOutput(BaseModel):
    text: str
    site: str
    workspace: str


def echo_app(settings):
    app = create_app(settings)

    async def echo(payload: EchoInput, principal: Principal = Depends(require_skill(SKILL))):
        await asyncio.sleep(0)
        return EchoOutput(text=payload.text, site=principal.site, workspace=principal.workspace_id)

    register_tool(app, SKILL, "translate", echo, response_model=EchoOutput)
    return app


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error", "trace_id"}
    assert set(body["error"]) == {"code", "message", "retryable"}
    assert body["error"]["code"] == code
    assert body["trace_id"] == response.headers["x-trace-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", body["trace_id"])
    return body


def test_health_and_no_unimplemented_or_management_schema_routes(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        for path in ("/openapi.json", "/docs", "/redoc", "/not-found"):
            assert_error(client.get(path), 404, "NOT_FOUND")
        assert_error(client.post(PATH, headers={"X-API-Key": CN_KEY}, json={}), 404, "NOT_FOUND")
    assert app.openapi()["paths"] == {}


@pytest.mark.parametrize("headers", [
    {}, {"X-API-Key": "wrong-key"}, {"Authorization": "Bearer " + CN_KEY},
    [("X-API-Key", CN_KEY), ("X-API-Key", CN_KEY)], {"X-API-Key": "x" * 257},
])
def test_invalid_authentication_is_rejected_before_body_parsing(settings, headers):
    with TestClient(echo_app(settings)) as client:
        response = client.post(PATH + "?api_key=" + CN_KEY, headers=headers, content="not-json")
    assert_error(response, 401, "AUTHENTICATION_FAILED")


def test_api_keys_bind_distinct_workspace_scopes_with_concurrent_requests(settings):
    with TestClient(echo_app(settings)) as client:
        def call(index):
            key, site = (CN_KEY, "cn") if index % 2 else (GLOBAL_KEY, "global")
            response = client.post(PATH, headers={"X-API-Key": key}, json={"text": f"request-{index}"})
            assert response.status_code == 200
            assert response.json() == {"text": f"request-{index}", "site": site, "workspace": f"{site}-private-space"}
            return response.headers["x-trace-id"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            traces = list(pool.map(call, range(24)))
    assert len(set(traces)) == 24


def test_requested_site_cannot_override_credential_scope_and_extra_body_fields_fail(settings):
    with TestClient(echo_app(settings)) as client:
        response = client.post(PATH + "?site=global&workspace=global-private-space",
                               headers={"X-API-Key": CN_KEY}, json={"text": "hello"})
        assert response.json()["site"] == "cn"
        response = client.post(PATH, headers={"X-API-Key": CN_KEY}, json={"text": "hello", "site": "global"})
    assert_error(response, 422, "INVALID_REQUEST")


def test_skill_allowlist_is_enforced(settings):
    app = create_app(settings)
    called = []

    async def voices():
        called.append(True)
        return {"status": "test-only"}

    class VoiceResponse(BaseModel):
        status: str

    register_tool(app, "iflytek-hyper-tts", "list_voices", voices, response_model=VoiceResponse)
    path = "/v1/skills/iflytek-hyper-tts/list_voices"
    with TestClient(app) as client:
        assert_error(client.get(path, headers={"X-API-Key": GLOBAL_KEY}), 403, "FORBIDDEN")
        assert not called
        assert client.get(path, headers={"X-API-Key": CN_KEY}).status_code == 200


def test_validation_errors_and_access_logs_do_not_echo_input_or_credentials(settings, caplog):
    private = "private-contract-text-" * 5
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    with TestClient(echo_app(settings)) as client:
        response = client.post(PATH + "?private=" + private,
                               headers={"X-API-Key": CN_KEY, "X-Trace-Id": "caller-controlled-secret"},
                               json={"text": private})
    body = assert_error(response, 422, "INVALID_REQUEST")
    records = " ".join(record.getMessage() for record in caplog.records if record.name == LOGGER.name)
    for value in (private, CN_KEY, "cn-private-space", "caller-controlled-secret"):
        assert value not in response.text
        assert value not in records
    assert body["trace_id"] in records
    assert "iflytek_translate__translate" in records


@pytest.mark.parametrize("code,status,retryable", [
    (ErrorCode.CONFLICT, 409, False), (ErrorCode.RATE_LIMITED, 429, True),
    (ErrorCode.UPSTREAM_PERMISSION_DENIED, 502, False), (ErrorCode.UPSTREAM_QUOTA_EXCEEDED, 502, False),
    (ErrorCode.UPSTREAM_ERROR, 502, False), (ErrorCode.UPSTREAM_PROTOCOL_ERROR, 502, False),
    (ErrorCode.DEPENDENCY_UNAVAILABLE, 503, False), (ErrorCode.TIMEOUT, 504, False),
    (ErrorCode.NOT_FOUND, 404, False),
])
def test_adapter_error_categories_are_distinct(settings, code, status, retryable):
    app = create_app(settings)

    async def failed():
        raise ServiceError(code)

    register_tool(app, SKILL, "translate", failed, response_model=EchoOutput)
    with TestClient(app) as client:
        body = assert_error(client.post(PATH, headers={"X-API-Key": CN_KEY}), status, code)
    assert body["error"]["retryable"] is retryable


@pytest.mark.parametrize("kind,status,code", [
    ("exception", 500, "INTERNAL_ERROR"), ("bad_response", 500, "INTERNAL_ERROR"),
    ("timeout", 504, "TIMEOUT"), ("http", 503, "DEPENDENCY_UNAVAILABLE"),
])
def test_unexpected_errors_and_upstream_details_are_redacted(settings, kind, status, code, caplog):
    app = create_app(settings)
    private = "private-api-token-and-file-path"

    async def failed():
        if kind == "exception":
            raise RuntimeError(private)
        if kind == "timeout":
            raise TimeoutError(private)
        if kind == "http":
            raise HTTPException(503, private, headers={"X-Upstream-Secret": private})
        return {"text": private}  # Missing required response fields.

    register_tool(app, SKILL, "translate", failed, response_model=EchoOutput)
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    with TestClient(app) as client:
        response = client.post(PATH, headers={"X-API-Key": CN_KEY})
    assert_error(response, status, code)
    assert private not in response.text
    assert "X-Upstream-Secret" not in response.headers
    assert private not in caplog.text


def test_wrong_method_and_trailing_slash_use_the_uniform_error_contract(settings):
    with TestClient(echo_app(settings)) as client:
        response = client.get(PATH, headers={"X-API-Key": CN_KEY})
        assert_error(response, 405, "METHOD_NOT_ALLOWED")
        assert response.headers["Allow"] == "POST"
        assert_error(client.post(PATH + "/", headers={"X-API-Key": CN_KEY}, json={"text": "hello"}), 404, "NOT_FOUND")


def test_inventory_and_registration_enforce_the_planned_route_contract(settings):
    tools = [Tool(skill, action) for skill, actions in SKILL_TOOLS.items() for action in actions]
    assert len(SKILL_TOOLS) == 11 and len(tools) == len({tool.operation_id for tool in tools}) == 24
    app = echo_app(settings)
    operation = app.openapi()["paths"][PATH]["post"]
    assert operation["operationId"] == "iflytek_translate__translate"
    assert operation["security"] == [{"ServiceApiKey": []}]
    assert operation["requestBody"]["content"]["application/json"]["schema"]
    assert app.openapi()["components"]["securitySchemes"]["ServiceApiKey"] == {
        "type": "apiKey", "in": "header", "name": "X-API-Key",
    }

    async def endpoint(payload: EchoInput):
        return payload

    with pytest.raises(ValueError, match="already registered"):
        register_tool(app, SKILL, "translate", endpoint, response_model=EchoOutput)
    with pytest.raises(ValueError, match="inventory"):
        register_tool(app, "unknown-skill", "run", endpoint, response_model=EchoOutput)
    with pytest.raises(ValueError, match="request body"):
        register_tool(app, "iflytek-hyper-tts", "list_voices", endpoint, response_model=EchoOutput)
    assert "/v1/skills/iflytek-hyper-tts/list_voices" not in {route.path for route in app.routes}


def test_query_tool_has_query_parameters_and_no_body(settings):
    app = create_app(settings)

    async def query(request: Request, job_id: str):
        return {"text": job_id, "site": request.state.principal.site,
                "workspace": request.state.principal.workspace_id}

    register_tool(app, "iflytek-speed-transcription", "get_task", query, response_model=EchoOutput)
    path = "/v1/skills/iflytek-speed-transcription/get_task"
    operation = app.openapi()["paths"][path]["get"]
    assert "requestBody" not in operation
    assert any(parameter["name"] == "job_id" and parameter["in"] == "query" for parameter in operation["parameters"])


def test_get_body_hidden_in_a_dependency_is_rejected_before_registration(settings):
    app = create_app(settings)

    def body_dependency(payload: EchoInput):
        return payload

    async def query(payload: EchoInput = Depends(body_dependency)):
        return payload

    with pytest.raises(ValueError, match="request body"):
        register_tool(app, "iflytek-speed-transcription", "get_task", query, response_model=EchoOutput)
    assert app.openapi()["paths"] == {}


def test_new_task_acceptance_is_explicitly_202_with_a_concrete_response_model(settings):
    app = create_app(settings)

    class Accepted(BaseModel):
        job_id: str
        status: str

    async def accept():
        return Accepted(job_id="test-only-job", status="queued")

    register_tool(app, SKILL, "translate", accept, response_model=Accepted, status_code=202)
    with TestClient(app) as client:
        response = client.post(PATH, headers={"X-API-Key": CN_KEY})
        assert response.status_code == 202
        assert response.json() == {"job_id": "test-only-job", "status": "queued"}
