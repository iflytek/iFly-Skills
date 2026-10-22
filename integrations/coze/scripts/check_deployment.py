"""Check one deployed HTTPS backend without creating tasks or paid upstream calls."""

import argparse
from http.client import HTTPException
import json
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.catalog import SKILL_TOOLS, Tool
from app.config import backend_url, load_settings, read_config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the service key to a redirected URL.


def request_json(opener, url, *, key=None, data=None):
    headers = {"Accept": "application/json"}
    if key is not None:
        headers["X-API-Key"] = key
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        response = opener.open(request, timeout=80)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Response too large")
        return response.status, json.loads(raw)


def check(values, site, *, check_voices=False, all_tools=False, opener=None):
    # Runtime and check use the same grants; no process-environment overrides or
    # platform tokens are needed. No fallback to another site's backend address.
    settings = load_settings(environ=values)
    grant = next((grant for grant in settings.grants if grant.principal.site == site), None)
    if grant is None:
        raise ValueError("Selected site is not enabled")
    base = backend_url(values.get(f"COZE_{site.upper()}_BACKEND_BASE_URL", ""))
    skill = next(skill for skill in SKILL_TOOLS if skill in grant.principal.allowed_skills)
    # Every current POST model requires input. An empty body validates the live
    # route and authentication without executing a Skill or spending quota.
    action = next(action for action in SKILL_TOOLS[skill] if Tool(skill, action).method == "POST")
    path = Tool(skill, action).path
    if check_voices and "iflytek-hyper-tts" not in grant.principal.allowed_skills:
        raise ValueError("Voice-list check requires the hyper-TTS grant")
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    checks = {}

    def probe(name, url, expected_status, predicate, **kwargs):
        try:
            status, payload = request_json(opener, url, **kwargs)
            checks[name] = {"passed": status == expected_status and predicate(payload), "http_status": status}
        except (OSError, HTTPException, ValueError, TypeError, KeyError):
            checks[name] = {"passed": False, "reason": "transport_or_response_error"}

    def error_is(code):
        return lambda payload: isinstance(payload, dict) and isinstance(payload.get("error"), dict) and payload["error"].get("code") == code

    probe("health", base + "/healthz", 200, lambda payload: payload == {"status": "ok"})
    probe("unauthenticated", base + path, 401, error_is("AUTHENTICATION_FAILED"), data=b"{}")
    wrong_key = "invalid-deployment-probe-" + "x" * 32
    while wrong_key in {item.api_key for item in settings.grants}:
        wrong_key += "x"
    probe("invalid_key", base + path, 401, error_is("AUTHENTICATION_FAILED"), key=wrong_key, data=b"{}")
    probe("authenticated_route", base + path, 422, error_is("INVALID_REQUEST"), key=grant.api_key, data=b"{}")
    if all_tools:
        for skill, actions in SKILL_TOOLS.items():
            if skill not in grant.principal.allowed_skills:
                continue
            for action in actions:
                tool = Tool(skill, action)
                name = f"tool:{skill}/{action}"
                if action == "list_voices":
                    continue  # Executed once below; this tool has no upstream call.
                # Invalid input reaches validation, never the business handler.
                # get_training_text has a default, so omit-only probing is unsafe.
                suffix = "?text_id=0" if action == "get_training_text" else "?job_id=invalid"
                probe(name, base + tool.path + (suffix if tool.method == "GET" else ""),
                      422, error_is("INVALID_REQUEST"), key=grant.api_key,
                      **({"data": b"{}"} if tool.method == "POST" else {}))
    if check_voices or (all_tools and "iflytek-hyper-tts" in grant.principal.allowed_skills):
        probe("voice_list", base + Tool("iflytek-hyper-tts", "list_voices").path, 200,
              lambda payload: isinstance(payload, dict) and isinstance(payload.get("free_voices"), list)
              and isinstance(payload.get("all_voices"), list) and bool(payload["all_voices"]), key=grant.api_key)
    return {"site": site, "passed": all(item["passed"] for item in checks.values()), "checks": checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=("cn", "global"), required=True)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--check-voices", action="store_true", help="Also execute the built-in voice-list tool (no upstream call).")
    parser.add_argument("--all-tools", action="store_true", help="Check every enabled tool route with invalid input, plus the non-billable voice list; does not verify upstream permissions.")
    args = parser.parse_args(argv)
    try:
        report = check(read_config(args.env_file), args.site, check_voices=args.check_voices,
                       all_tools=args.all_tools)
    except (OSError, ValueError, StopIteration):
        report = {"site": args.site, "passed": False,
                  "reason": "invalid_configuration",
                  "hint": "Check the config file, enabled site, runtime grants and this site's HTTPS BACKEND_BASE_URL; --check-voices requires iflytek-hyper-tts."}
    # Neither backend URLs, credentials, workspace IDs nor raw responses are printed.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
