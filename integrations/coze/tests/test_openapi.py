"""Validate 3.0 schemas and real HTTP envelopes, without paid service calls."""

import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from openapi_schema_validator import OAS30Validator
from openapi_spec_validator import OpenAPIV30SpecValidator
import pytest
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

from app.catalog import SKILL_IDS, SKILL_TOOLS, Tool
from app.config import Principal, Settings, SiteGrant
from app.main import create_app
from app.openapi import TEMPLATE_BASE_URL, backend_url, export_documents, schema_30
from app.tools import CONTRACTS
from scripts.export_openapi import main, serialize


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def documents():
    return export_documents()


def validator(doc, schema):
    # Scope local component references to their own per-Skill document.
    resource = {"allOf": [schema], "components": doc["components"]}
    registry = Registry().with_resource("https://schema.example/instance", Resource(resource, DRAFT4))
    return OAS30Validator({"$ref": "https://schema.example/instance"}, registry=registry)


def references(node):
    if isinstance(node, dict):
        if "$ref" in node:
            yield node["$ref"]
        for value in node.values():
            yield from references(value)
    elif isinstance(node, list):
        for value in node:
            yield from references(value)


@pytest.mark.parametrize("skill", sorted(SKILL_IDS))
def test_standalone_specs_match_routes_auth_and_models(documents, skill):
    doc = documents[skill]
    OpenAPIV30SpecValidator(doc).validate()
    assert doc["openapi"] == "3.0.3"
    assert doc["servers"] == [{"url": TEMPLATE_BASE_URL}]
    assert set(doc["paths"]) == {Tool(skill, action).path for action in SKILL_TOOLS[skill]}
    assert doc["components"]["securitySchemes"] == {"ServiceApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}
    reachable = set()
    pending = list(references(doc["paths"]))
    while pending:
        ref = pending.pop()
        assert ref.startswith("#/components/schemas/")
        name = ref.rsplit("/", 1)[1]
        if name not in reachable:
            reachable.add(name)
            pending.extend(references(doc["components"]["schemas"][name]))
    assert reachable == set(doc["components"]["schemas"])
    for action, (request_model, response_model) in CONTRACTS[skill].items():
        tool = Tool(skill, action)
        assert set(doc["paths"][tool.path]) == {tool.method.lower()}
        operation = doc["paths"][tool.path][tool.method.lower()]
        assert operation["operationId"] == tool.operation_id
        assert operation["summary"] and operation["description"]
        assert operation["security"] == [{"ServiceApiKey": []}]
        if request_model:
            assert operation["requestBody"]["required"]
            ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
            schema = doc["components"]["schemas"][ref.rsplit("/", 1)[1]]
            assert set(schema["properties"]) == set(request_model.model_fields)
            assert set(schema.get("required", [])) == {key for key, field in request_model.model_fields.items() if field.is_required()}
            assert all(prop.get("description") for prop in schema["properties"].values())
        else:
            assert "requestBody" not in operation
            params = operation.get("parameters", [])
            expected = set() if action == "list_voices" else {"text_id" if action == "get_training_text" else "job_id"}
            assert {p["name"] for p in params} == expected
            assert all(p["in"] == "query" and p["description"] for p in params)
            if expected == {"job_id"}:
                assert params[0]["required"] and params[0]["schema"]["pattern"] == r"^[a-f0-9]{32}$"
        success = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        properties = doc["components"]["schemas"][success.rsplit("/", 1)[1]]["properties"]
        assert set(properties) == set(response_model.model_fields)
        assert all(prop.get("description") for prop in properties.values())
        for code, response in operation["responses"].items():
            if code != "200":
                assert response["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorEnvelope"


def test_generated_files_are_current_and_ids_unique(documents):
    assert {p.stem for p in (ROOT / "schemas").glob("*.json")} == SKILL_IDS
    ids = []
    for skill, doc in documents.items():
        assert (ROOT / "schemas" / (skill + ".json")).read_text(encoding="utf-8") == serialize(doc)
        ids.extend(op["operationId"] for path in doc["paths"].values() for op in path.values())
    assert len(ids) == len(set(ids)) == 24


def test_export_covers_actual_application_routes(documents):
    settings = Settings((SiteGrant(Principal("cn", "test", SKILL_IDS), "schema-test-" + "a" * 32),))
    app = create_app(settings)
    actual = {(route.path, method, route.operation_id) for route in app.routes if route.include_in_schema
              for method in route.methods}
    exported = {(path, method.upper(), operation["operationId"]) for doc in documents.values()
                for path, methods in doc["paths"].items() for method, operation in methods.items()}
    assert actual == exported


@pytest.mark.parametrize("skill, action", [
    (skill, action) for skill, actions in CONTRACTS.items() for action in actions
    if action.startswith("get_") and action != "get_training_text"
])
def test_job_query_constraints_match_schema_and_http(documents, skill, action):
    tool = Tool(skill, action)
    operation = documents[skill]["paths"][tool.path]["get"]
    parameter = operation["parameters"][0]
    assert parameter["name"] == "job_id" and parameter["required"]
    query = validator(documents[skill], parameter["schema"])
    key = "schema-test-" + "a" * 32
    settings = Settings((SiteGrant(Principal("cn", "test", SKILL_IDS), key),))
    calls = []

    class Runtime:
        async def start(self): pass
        async def close(self): pass
        async def execute(self, principal, skill, action, payload):
            calls.append(payload)
            return {"job_id": payload["job_id"], "status": "running"}

    with TestClient(create_app(settings, runtime=Runtime())) as client:
        for job_id in ("", "not-a-job-id", "a" * 31, "a" * 33, "A" * 32):
            assert not query.is_valid(job_id)
            response = client.get(tool.path, headers={"X-API-Key": key}, params={"job_id": job_id})
            assert response.status_code == 422
            validator(documents[skill], operation["responses"]["422"]["content"]["application/json"]["schema"]).validate(response.json())
        assert client.get(tool.path, headers={"X-API-Key": key}).status_code == 422
        assert not calls
        query.validate("a" * 32)
        response = client.get(tool.path, headers={"X-API-Key": key}, params={"job_id": "a" * 32})
        assert response.status_code == 200
        assert calls == [{"job_id": "a" * 32}]
        validator(documents[skill], operation["responses"]["200"]["content"]["application/json"]["schema"]).validate(response.json())


def test_conversion_preserves_nullable_refs_enums_and_numeric_boundaries(documents):
    doc = documents["iflytek-voiceclone-tts"]
    job = validator(doc, {"$ref": "#/components/schemas/Job_TrainingResult_"})
    for result in (None, {"stage": "submitted", "res_id": None, "failure_reason": None, "upstream_status": 2},
                   {"stage": "failed", "failure_reason": "audio_text_mismatch"}):
        job.validate({"job_id": "a" * 32, "status": "running", "result": result, "error_code": None})
    for result in ({}, [], "text", {"stage": "invalid"}, {"stage": "failed", "failure_reason": "raw secret"}):
        assert not job.is_valid({"job_id": "a" * 32, "status": "running", "result": result})
    upload = validator(doc, {"$ref": "#/components/schemas/UploadSample"})
    payload = {"request_id": "one", "job_id": "a" * 32, "audio_url": "https://files.example/sample.wav", "text_id": 1, "seg_id": 1}
    upload.validate(payload)
    for value in (0, -1, None, "1", 1.5):
        assert not upload.is_valid({**payload, "seg_id": value})
    clone = validator(doc, {"$ref": "#/components/schemas/CloneSpeech"})
    clone.validate({"res_id": "resource", "text": "Hello", "format": "mp3"})
    assert not clone.is_valid({"res_id": "resource", "text": "Hello", "format": "wav"})
    image = documents["iflytek-image-understanding"]
    analyze = validator(image, {"$ref": "#/components/schemas/Analyze"})
    for value, valid in ((0, False), (0.1, True), (1, True), (1.1, False)):
        assert analyze.is_valid({"image_url": "https://files.example/i.png", "question": "What?", "temperature": value}) == valid


def test_conversion_does_not_rewrite_data_and_rejects_unsupported_keywords():
    data = {"const": "a property name", "type": "null"}
    schema = {"type": "object", "properties": {"const": {"type": "string"}}, "example": data, "default": data}
    assert schema_30(schema) == schema
    assert schema_30({"$ref": "#/components/schemas/Item", "description": "Details"}) == {
        "allOf": [{"$ref": "#/components/schemas/Item"}], "description": "Details"}
    for unsupported in ({"unevaluatedProperties": False}, {"type": ["string", "null"]}, {"$dynamicRef": "#something"}, True,
                        {"anyOf": [True, {"type": "null"}]}, {"anyOf": []},
                        {"anyOf": [{"type": ["string", "null"]}, {"type": "null"}]}):
        with pytest.raises(ValueError):
            schema_30(unsupported)


@pytest.mark.parametrize("schema, samples", [
    ({"anyOf": [{"type": "string", "maxLength": 3}, {"type": "null"}], "maxLength": 10},
     [None, "", "abc", "abcd", "x" * 11, 5]),
    ({"anyOf": [{"type": "string", "pattern": "^a"}, {"type": "null"}], "pattern": "z$"},
     [None, "az", "abc", "xyz"]),
    ({"anyOf": [{"type": "string", "not": {"enum": ["bad"]}}, {"type": "null"}]},
     [None, "good", "bad", False]),
    ({"anyOf": [{"type": "integer", "minimum": 5}, {"type": "null"}], "minimum": 2},
     [None, 1, 2, 4, 5, 10]),
])
def test_nullable_conversion_preserves_combined_constraint_semantics(schema, samples):
    original, exported = Draft202012Validator(schema), OAS30Validator(schema_30(schema))
    assert [exported.is_valid(value) for value in samples] == [original.is_valid(value) for value in samples]


@pytest.mark.parametrize("url", [
    "http://backend.example", "https://127.0.0.1", "https://[::1]", "https://localhost",
    "https://api.coze.cn", "https://api.coze.com", "https://a:b@backend.example",
    "https://backend.example?token=private", "https://backend.example/#part", "https://backend.example:bad",
    "https://backend.example/../proxy", "https://backend.example/v1/skills/iflytek-translate",
    "https://backend.example/%2fhidden", "https://backend.example/\n", "https://-bad.example",
])
def test_deployment_address_rejects_invalid_or_wrong_service_urls(url):
    with pytest.raises(ValueError):
        backend_url(url)


def test_site_export_is_independent_and_check_never_writes(tmp_path, capsys):
    config = tmp_path / ".env"
    config.write_text("COZE_CN_BACKEND_BASE_URL=https://cn.example/proxy/\nCOZE_GLOBAL_BACKEND_BASE_URL=https://global.example:8443/\nCOZE_CN_API_TOKEN=PRIVATE-TOKEN\n", encoding="utf-8")
    for site, expected in (("cn", "https://cn.example/proxy"), ("global", "https://global.example:8443")):
        output = tmp_path / site
        args = ["--site", site, "--env-file", str(config), "--output-dir", str(output)]
        assert main(args) == 0
        for file in output.glob("*.json"):
            raw = file.read_text(encoding="utf-8")
            doc = json.loads(raw)
            assert doc["servers"] == [{"url": expected}]
            assert "PRIVATE-TOKEN" not in raw
            for path in doc["paths"]:
                assert (expected + path).count("/v1/skills/") == 1
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in output.iterdir()}
        assert main(args + ["--check"]) == 0
        assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in output.iterdir()}
        stale = next(output.glob("*.json"))
        stale.write_text("{}", encoding="utf-8")
        assert main(args + ["--check"]) == 1
        assert stale.read_text() == "{}"
    assert "PRIVATE-TOKEN" not in capsys.readouterr().out
    config.write_text("COZE_CN_BACKEND_BASE_URL=\nCOZE_GLOBAL_BACKEND_BASE_URL=https://global.example\n", encoding="utf-8")
    assert main(["--site", "cn", "--env-file", str(config), "--output-dir", str(tmp_path / "absent")]) == 1
    assert not (tmp_path / "absent").exists()
    assert "COZE_CN_BACKEND_BASE_URL" in capsys.readouterr().err


def test_env_file_requires_a_selected_site_and_does_not_write(tmp_path, capsys):
    output = tmp_path / "schemas"
    for args in ([], ["--base-url", "https://backend.example"]):
        with pytest.raises(SystemExit) as exc:
            main(args + ["--env-file", str(tmp_path / "private.env"), "--output-dir", str(output)])
        assert exc.value.code == 2
        assert "--env-file requires --site" in capsys.readouterr().err
        assert not output.exists()


def test_cli_errors_are_actionable_without_disclosing_config_values(tmp_path, capsys):
    output = tmp_path / "schemas"
    args = ["--output-dir", str(output)]
    assert main(args + ["--base-url", "https://secret-token@backend.example"]) == 1
    error = capsys.readouterr().err
    assert "HTTPS backend domain" in error and "secret-token" not in error
    config = tmp_path / ".env"
    config.write_text("UNKNOWN=secret-token", encoding="utf-8")
    assert main(args + ["--site", "cn", "--env-file", str(config)]) == 1
    error = capsys.readouterr().err
    assert "configuration file" in error and "secret-token" not in error
    assert not output.exists()


def test_export_cli_works_outside_repository_without_credentials(tmp_path):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "export_openapi.py"),
                             "--output-dir", str(tmp_path / "schemas")], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(list((tmp_path / "schemas").glob("*.json"))) == 11


def test_actual_http_envelopes_validate_against_exported_contract(documents):
    skill = "iflytek-translate"
    key = "schema-test-" + "a" * 32
    settings = Settings((SiteGrant(Principal("cn", "test", frozenset({skill})), key),))

    class Runtime:
        async def start(self): pass
        async def close(self): pass
        async def execute(self, principal, skill, action, payload):
            return {"src": payload["text"], "dst": "Hello", "from_lang": "cn", "to_lang": "en"}

    doc = documents[skill]
    path = Tool(skill, "translate").path
    responses = doc["paths"][path]["post"]["responses"]
    with TestClient(create_app(settings, runtime=Runtime())) as client:
        cases = [client.post(path, json={"text": "test"}),
                 client.post(path, headers={"X-API-Key": key}, json={}),
                 client.post(path, headers={"X-API-Key": key}, json={"text": "你好"})]
    assert [r.status_code for r in cases] == [401, 422, 200]
    for response in cases:
        schema = responses[str(response.status_code)]["content"]["application/json"]["schema"]
        validator(doc, schema).validate(response.json())
