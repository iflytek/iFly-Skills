"""Check one Coze site's configuration; optionally read its workspace list.

This is a preparation check, not the backend's runtime configuration loader.
It never creates/publishes resources or prints tokens or workspace names/IDs.
"""

import argparse
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import read_config


BASES = {"cn": "https://api.coze.cn", "global": "https://api.coze.com"}
SUFFIXES = ("API_BASE_URL", "WORKSPACE_ID", "API_TOKEN", "BACKEND_BASE_URL", "BACKEND_API_KEY")
DEFAULT_ENV = Path(__file__).resolve().parents[1] / ".env"


def validate(values, site, require_backend=False):
    prefix = f"COZE_{site.upper()}_"
    config = {suffix: values.get(prefix + suffix, "") for suffix in SUFFIXES}
    required = SUFFIXES if require_backend else SUFFIXES[:3]
    errors = [f"Missing {prefix}{key}" for key in required if not config[key]]
    if config["API_BASE_URL"] != BASES[site]:
        errors.append(f"{prefix}API_BASE_URL must equal the selected site's official URL")
    if any(c.isspace() for c in config["API_TOKEN"]):
        errors.append(f"{prefix}API_TOKEN contains whitespace")
    if config["BACKEND_BASE_URL"]:
        try:
            url = urllib.parse.urlsplit(config["BACKEND_BASE_URL"])
            host = url.hostname or ""
            valid = (url.scheme == "https" and "." in host and not url.username
                     and not url.password and not url.query and not url.fragment
                     and host not in {"api.coze.cn", "api.coze.com"})
            _ = url.port
            try:
                ipaddress.ip_address(host)
                valid = False
            except ValueError:
                pass
        except ValueError:
            valid = False
        if not valid:
            errors.append(f"{prefix}BACKEND_BASE_URL must be an HTTPS service domain without credentials/query/fragment")
    other = "GLOBAL" if site == "cn" else "CN"
    service_key = config["BACKEND_API_KEY"]
    if service_key and service_key == values.get(f"COZE_{other}_BACKEND_API_KEY"):
        errors.append("The two sites must use separate backend service keys")
    if service_key and service_key in {values.get("COZE_CN_API_TOKEN"), values.get("COZE_GLOBAL_API_TOKEN")}:
        errors.append("A platform token must not be reused as a backend service key")
    return config, errors


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a Bearer token to a redirect destination.


class CurlOpener:
    """Use the system TLS implementation without putting tokens in argv."""

    def open(self, request, timeout):
        def quote(value):
            return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

        config = "url = " + quote(request.full_url) + "\n"
        for key, value in request.header_items():
            config += "header = " + quote(key + ": " + value) + "\n"
        try:
            result = subprocess.run(
                ["curl", "--disable", "--silent", "--show-error", "--proto", "=https",
                 "--max-time", str(timeout), "--write-out", "\n%{http_code}", "--config", "-"],
                input=config, text=True, encoding="utf-8", capture_output=True, timeout=timeout + 5,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("curl timed out") from None
        if result.returncode:
            raise OSError("curl connection failed")  # Do not echo stderr or request configuration.
        body, separator, status = result.stdout.rpartition("\n")
        if not separator or not status.isdigit():
            raise ValueError("Invalid curl response")
        if int(status) >= 300:
            raise urllib.error.HTTPError(request.full_url, int(status), "HTTP error", {},
                                         io.BytesIO(body.encode("utf-8")))
        response = io.StringIO(body)
        response.status = int(status)
        return response


def verify_workspace(config, opener=None):
    opener = opener or urllib.request.build_opener(NoRedirect())
    result = {"method": "GET", "path": "/v1/workspaces", "verified": False}
    target = config["WORKSPACE_ID"]
    result["workspace_fingerprint"] = hashlib.sha256(target.encode()).hexdigest()[:12]
    for page in range(1, 101):
        url = config["API_BASE_URL"] + f"/v1/workspaces?page_num={page}&page_size=50"
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + config["API_TOKEN"], "Accept": "application/json",
        })
        try:
            with opener.open(request, timeout=20) as response:
                result["http_status"] = response.status
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            result.update(http_status=exc.code, reason="http_error")
            try:
                error = json.load(exc)
                if isinstance(error, dict) and isinstance(error.get("code"), int):
                    result["business_code"] = error["code"]
                    if error["code"] == 4101 and "listWorkspace" in str(error.get("msg", "")):
                        result["required_permission"] = "listWorkspace"
            except (ValueError, OSError, TypeError):
                pass
            exc.close()
            return result
        except (urllib.error.URLError, TimeoutError, OSError):
            result["reason"] = "transport_error"
            return result
        except (ValueError, UnicodeError):
            result["reason"] = "invalid_json_response"
            return result
        if not isinstance(payload, dict):
            result["reason"] = "unexpected_response"
            return result
        code = payload.get("code")
        # Only numeric business codes enter the report; raw response text may contain secrets.
        result["business_code"] = code if isinstance(code, int) else None
        if code != 0:
            result["reason"] = "business_error"
            return result
        data = payload.get("data")
        workspaces = data.get("workspaces") if isinstance(data, dict) else None
        if not isinstance(workspaces, list):
            result["reason"] = "unexpected_response"
            return result
        for workspace in workspaces:
            if isinstance(workspace, dict) and str(workspace.get("id")) == target:
                role = workspace.get("role_type")
                result.update(verified=True, reason="target_workspace_visible",
                              role=role if role in {"owner", "admin", "member"} else "unreported")
                return result
        total = data.get("total_count")
        if len(workspaces) < 50 or (isinstance(total, int) and page * 50 >= total):
            result["reason"] = "target_workspace_not_in_accessible_list"
            return result
    result["reason"] = "pagination_limit_reached"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=BASES, required=True)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--online", action="store_true", help="Read /v1/workspaces using the selected site's token")
    parser.add_argument("--transport", choices=("urllib", "curl"), default="urllib")
    parser.add_argument("--require-backend", action="store_true", help="Also require deployment URL and service key")
    args = parser.parse_args()
    try:
        values = read_config(args.env_file)
        config, errors = validate(values, args.site, args.require_backend)
    except (OSError, UnicodeError):
        errors = ["Cannot read configuration file as UTF-8"]
    except ValueError as exc:
        errors = [str(exc)]
    report = {"site": args.site, "configuration_valid": not errors, "errors": errors}
    if args.online and not errors:
        report["transport"] = args.transport
        report["workspace_check"] = verify_workspace(config, CurlOpener() if args.transport == "curl" else None)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if errors or (args.online and not report["workspace_check"]["verified"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
