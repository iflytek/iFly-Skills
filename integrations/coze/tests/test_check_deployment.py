"""The deployment probe must not spend quota, follow redirects or expose secrets."""

from io import BytesIO
from http.client import BadStatusLine, IncompleteRead
import json
import urllib.request
import urllib.response

from fastapi.testclient import TestClient
import pytest

from app.catalog import SKILL_IDS
from app.config import load_settings
from app.main import create_base_app
from app.tools import attach_tools
from scripts.check_deployment import check, main, NoRedirect, request_json


def configuration(skill="iflytek-translate", site="cn"):
    return {
        "COZE_ENABLED_SITES": site,
        f"COZE_{site.upper()}_WORKSPACE_ID": "private-workspace",
        f"COZE_{site.upper()}_BACKEND_API_KEY": "deployment-key-" + "x" * 32,
        f"COZE_{site.upper()}_ALLOWED_SKILLS": skill,
        f"COZE_{site.upper()}_BACKEND_BASE_URL": "https://backend.example/coze/",
    }


class Response(BytesIO):
    def __init__(self, status, body):
        super().__init__(body)
        self.status = status


class AppOpener:
    def __init__(self, values):
        app = create_base_app(load_settings(environ=values))
        attach_tools(app)
        # No Runtime is attached. If any probe executes business logic, it fails.
        self.client = TestClient(app)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        assert request.full_url.startswith("https://backend.example/coze/")
        path = request.full_url.removeprefix("https://backend.example/coze")
        result = self.client.request(request.get_method(), path, headers=dict(request.header_items()), content=request.data)
        return Response(result.status_code, result.content)


@pytest.mark.parametrize("skill", sorted(SKILL_IDS))
def test_every_skill_supports_a_non_billable_authenticated_probe(skill):
    values = configuration(skill)
    opener = AppOpener(values)
    result = check(values, "cn", opener=opener)
    assert result["passed"]
    assert result["checks"]["authenticated_route"]["http_status"] == 422
    assert len(opener.requests) == 4
    assert all(request.data in (None, b"{}") for request in opener.requests)
    assert "private-workspace" not in json.dumps(result)
    assert values["COZE_CN_BACKEND_API_KEY"] not in json.dumps(result)


def test_site_is_independent_and_configuration_never_uses_platform_tokens():
    values = configuration(site="global")
    values["COZE_CN_BACKEND_BASE_URL"] = "https://wrong.example"
    assert check(values, "global", opener=AppOpener(values))["passed"]
    with pytest.raises(ValueError):
        check(values, "cn", opener=AppOpener(values))
    values["COZE_GLOBAL_BACKEND_BASE_URL"] = ""
    with pytest.raises(ValueError):
        check(values, "global", opener=AppOpener(values))


def test_redirects_cannot_forward_service_credentials():
    class RedirectSource(urllib.request.HTTPSHandler):
        def https_open(self, request):
            if request.full_url != "https://backend.example/":
                pytest.fail("Credential-bearing redirect was followed")
            response = urllib.response.addinfourl(BytesIO(b'{}'), {"Location": "https://elsewhere.example"}, request.full_url, 302)
            response.msg = "Moved"
            return response

    handler = NoRedirect()
    assert handler.redirect_request(None, None, 302, "Moved", {}, "https://elsewhere.example") is None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), handler, RedirectSource())
    status, _ = request_json(opener, "https://backend.example/", key="private-key")
    assert status == 302


@pytest.mark.parametrize("failure", [
    OSError("private-key / private-workspace / private-response"),
    BadStatusLine("private-response"),
    IncompleteRead(b"private-response"),
])
def test_probe_failures_are_actionable_without_echoing_responses_or_keys(failure):
    class FailingOpener:
        def open(self, request, timeout):
            raise failure

    result = check(configuration(), "cn", opener=FailingOpener())
    assert not result["passed"]
    assert all(not item["passed"] for item in result["checks"].values())
    assert "private" not in json.dumps(result)


def test_default_transport_does_not_route_keys_through_environment_proxy(monkeypatch):
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"https": "http://proxy.example:8080"})
    values = configuration()

    def direct_response(self, request):
        assert request.host == "backend.example"
        assert request._tunnel_host is None
        if request.full_url.endswith("/healthz"):
            status, payload = 200, {"status": "ok"}
        else:
            valid = request.get_header("X-api-key") == values["COZE_CN_BACKEND_API_KEY"]
            status = 422 if valid else 401
            payload = {"error": {"code": "INVALID_REQUEST" if valid else "AUTHENTICATION_FAILED"}}
        response = urllib.response.addinfourl(BytesIO(json.dumps(payload).encode()), {}, request.full_url, status)
        response.msg = "Probe"
        return response

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", direct_response)
    assert check(values, "cn")["passed"]


def test_voice_list_is_explicit_and_requires_its_grant():
    with pytest.raises(ValueError):
        check(configuration(), "cn", check_voices=True)

    class VoiceOpener(AppOpener):
        def open(self, request, timeout):
            if request.full_url.endswith("/list_voices"):
                self.requests.append(request)
                return Response(200, b'{"free_voices": [], "all_voices": [{"name": "example"}]}')
            return super().open(request, timeout)

    values = configuration("iflytek-hyper-tts")
    opener = VoiceOpener(values)
    assert check(values, "cn", check_voices=True, opener=opener)["passed"]
    assert len(opener.requests) == 5


def test_cli_configuration_error_does_not_print_sensitive_values(tmp_path, capsys):
    config = tmp_path / "deployment.env"
    values = configuration()
    values["COZE_CN_BACKEND_BASE_URL"] = "https://private-key@backend.example"
    config.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
    assert main(["--site", "cn", "--env-file", str(config)]) == 1
    report = capsys.readouterr().out
    assert "invalid_configuration" in report
    assert "private-key" not in report and "private-workspace" not in report


def test_unexpected_or_oversized_response_is_a_failed_check():
    class BadResponse:
        def open(self, request, timeout):
            return Response(200, b"x" * (1024 * 1024 + 1))

    assert not check(configuration(), "cn", opener=BadResponse())["passed"]


@pytest.mark.parametrize("site", ["cn", "global"])
def test_all_tool_probes_validate_without_executing_paid_operations(site):
    class VoiceOpener(AppOpener):
        def open(self, request, timeout):
            if request.full_url.endswith("/list_voices"):
                self.requests.append(request)
                return Response(200, b'{"free_voices": [], "all_voices": [{"name": "example"}]}')
            return super().open(request, timeout)

    values = configuration(",".join(sorted(SKILL_IDS)), site)
    opener = VoiceOpener(values)
    result = check(values, site, all_tools=True, opener=opener)
    assert result["passed"]
    tools = {name: item for name, item in result["checks"].items() if name.startswith("tool:")}
    assert len(tools) == 23
    assert all(item["http_status"] == 422 for item in tools.values())
    assert result["checks"]["voice_list"]["http_status"] == 200
    assert any(request.full_url.endswith("/get_training_text?text_id=0") for request in opener.requests)
    assert all(request.data in (None, b"{}") for request in opener.requests)
    assert "private-workspace" not in json.dumps(result)
    assert values[f"COZE_{site.upper()}_BACKEND_API_KEY"] not in json.dumps(result)


def test_all_tools_checks_only_allowed_skills_and_detects_a_missing_route():
    class MissingRoute(AppOpener):
        def open(self, request, timeout):
            if request.full_url.endswith("/get_task?job_id=invalid"):
                self.requests.append(request)
                return Response(404, b'{"error":{"code":"NOT_FOUND"}}')
            return super().open(request, timeout)

    values = configuration("iflytek-speed-transcription")
    opener = MissingRoute(values)
    result = check(values, "cn", all_tools=True, opener=opener)
    assert not result["passed"]
    assert result["checks"]["authenticated_route"]["passed"]
    assert not result["checks"]["tool:iflytek-speed-transcription/get_task"]["passed"]
    assert not any("voice" in request.full_url or "translate/" in request.full_url for request in opener.requests)
