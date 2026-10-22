"""Export the registered tools as standalone OpenAPI 3.0.3 documents.

This module builds route metadata only: no settings, credentials or runtime are loaded.
The conversion supports the schema vocabulary emitted by our models and fails on
new unsupported keywords rather than silently weakening the API contract.
"""

from copy import deepcopy

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .catalog import SKILL_TOOLS, Tool
from .config import backend_url
from .main import API_VERSION
from .tools import attach_tools


TEMPLATE_BASE_URL = "https://backend.example.com"
SCHEMA_KEYWORDS = frozenset({
    "$ref", "title", "description", "type", "format", "default", "enum", "const",
    "multipleOf", "maximum", "minimum", "exclusiveMaximum", "exclusiveMinimum",
    "maxLength", "minLength", "pattern", "maxItems", "minItems", "uniqueItems",
    "maxProperties", "minProperties", "required", "properties", "additionalProperties",
    "items", "allOf", "anyOf", "oneOf", "not", "nullable", "readOnly", "writeOnly",
    "deprecated", "example", "xml", "externalDocs", "discriminator",
})
SCHEMA_ANNOTATIONS = frozenset({"title", "description", "default", "example", "deprecated", "readOnly", "writeOnly"})


def schema_30(schema: dict) -> dict:
    """Convert a Schema Object, never arbitrary example/default/property data."""
    if not isinstance(schema, dict):
        raise ValueError("Boolean or non-object schemas are not supported in OpenAPI 3.0")
    unknown = set(schema) - SCHEMA_KEYWORDS
    if any(not key.startswith("x-") for key in unknown):
        raise ValueError("Unsupported OpenAPI schema keyword: " + ", ".join(sorted(unknown)))
    result = deepcopy(schema)
    kind = result.get("type")
    if kind == "null":
        if set(result) != {"type"}:
            raise ValueError("Unsupported constraints on a null schema")
        # OAS 3.0 has no null type. This branch admits null and nothing else.
        return {"type": "object", "nullable": True, "enum": [None]}
    if isinstance(kind, list):
        raise ValueError("Use explicit anyOf branches for union types")
    if "const" in result:
        const = result.pop("const")
        if "enum" in result and const not in result["enum"]:
            raise ValueError("Conflicting const and enum constraints")
        result["enum"] = [const]
    for exclusive, bound in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if exclusive in result and not isinstance(result[exclusive], bool):
            value = result.pop(exclusive)
            if not isinstance(value, (int, float)):
                raise ValueError("An exclusive bound must be numeric")
            if bound not in result or (value >= result[bound] if bound == "minimum" else value <= result[bound]):
                result[bound] = value
                result[exclusive] = True
    if "properties" in result:
        result["properties"] = {name: schema_30(prop) for name, prop in result["properties"].items()}
    for key in ("items", "not", "additionalProperties"):
        if key in result and not (key == "additionalProperties" and isinstance(result[key], bool)):
            result[key] = schema_30(result[key])
    for key in ("allOf", "anyOf", "oneOf"):
        if key in result:
            branches = result[key]
            if not isinstance(branches, list) or not branches or any(not isinstance(b, dict) for b in branches):
                raise ValueError("Schema composition requires a nonempty list of schema objects")
            # A nullable scalar can use the conventional 3.0 representation.
            nonnull = [b for b in branches if b != {"type": "null"}]
            if (key == "anyOf" and len(nonnull) == 1 and len(branches) == 2
                    and isinstance(nonnull[0].get("type"), str)
                    and nonnull[0]["type"] in {"string", "integer", "number", "boolean", "array", "object"}
                    and not set(nonnull[0]).intersection({"$ref", "allOf", "anyOf", "oneOf", "not"})
                    and set(result) <= SCHEMA_ANNOTATIONS | {"anyOf"}):
                # Only annotations may be merged. Outer constraints apply in
                # addition to branch constraints, and must not overwrite them.
                converted = schema_30(nonnull[0])
                converted["nullable"] = True
                if "enum" in converted and None not in converted["enum"]:
                    converted["enum"].append(None)
                result.pop(key)
                result = {**converted, **result}
            else:
                result[key] = [schema_30(branch) for branch in branches]
    if "$ref" in result and len(result) > 1:
        # 3.0 Reference Objects ignore siblings; preserve them in a Schema Object.
        ref = result.pop("$ref")
        result.setdefault("allOf", []).insert(0, {"$ref": ref})
    return result


def _content_30(content: dict) -> None:
    for media in content.values():
        if "schema" in media:
            media["schema"] = schema_30(media["schema"])


def export_documents(base_url: str = TEMPLATE_BASE_URL) -> dict[str, dict]:
    base = backend_url(base_url)
    app = FastAPI(version=API_VERSION)
    attach_tools(app)
    documents = {}
    for skill, actions in SKILL_TOOLS.items():
        paths = {Tool(skill, action).path for action in actions}
        routes = [route for route in app.routes if route.path in paths]
        if len(routes) != len(actions):
            raise ValueError("The registered tools do not match the Skill inventory")
        doc = get_openapi(title=skill, version=app.version, routes=routes, openapi_version="3.1.0")
        doc["openapi"] = "3.0.3"
        doc["info"]["description"] = "iFly-Skills API plugin. Configure the deployment's X-API-Key separately; credentials are never tool arguments."
        doc["servers"] = [{"url": base}]
        schemas = doc["components"]["schemas"]
        doc["components"]["schemas"] = {name: schema_30(schema) for name, schema in schemas.items()}
        for action in actions:
            tool = Tool(skill, action)
            operation = doc["paths"][tool.path][tool.method.lower()]
            if operation["operationId"] != tool.operation_id:
                raise ValueError("Unstable operation ID")
            for parameter in operation.get("parameters", []):
                parameter["schema"] = schema_30(parameter["schema"])
            if "requestBody" in operation:
                _content_30(operation["requestBody"]["content"])
            for response in operation["responses"].values():
                _content_30(response.get("content", {}))
        documents[skill] = doc
    return documents
