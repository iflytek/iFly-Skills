"""Offline checks for site isolation and redacted workspace verification."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error


SPEC = importlib.util.spec_from_file_location("check_config", Path(__file__).parents[1] / "scripts/check_config.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ConfigCheckTest(unittest.TestCase):
    def setUp(self):
        self.values = {"COZE_CN_API_BASE_URL": CHECK.BASES["cn"],
                       "COZE_CN_WORKSPACE_ID": "example-workspace", "COZE_CN_API_TOKEN": "test-secret"}
        self.config, errors = CHECK.validate(self.values, "cn")
        self.assertEqual(errors, [])

    def test_no_cross_site_fallback_or_wrong_domain(self):
        _, errors = CHECK.validate(self.values, "global")
        self.assertTrue(errors)
        self.values["COZE_CN_API_BASE_URL"] = CHECK.BASES["global"]
        self.assertTrue(CHECK.validate(self.values, "cn")[1])

    def test_deployment_config_is_required_only_when_requested(self):
        self.assertTrue(CHECK.validate(self.values, "cn", require_backend=True)[1])
        self.values.update(COZE_CN_BACKEND_BASE_URL="https://api.coze.cn", COZE_CN_BACKEND_API_KEY="test-secret")
        self.assertEqual(len(CHECK.validate(self.values, "cn", True)[1]), 2)

    def test_quoted_values_and_duplicate_key_errors_do_not_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text('\ufeffCOZE_CN_API_TOKEN="test-secret"\n', encoding="utf-8")
            self.assertEqual(CHECK.read_config(path)["COZE_CN_API_TOKEN"], "test-secret")
            path.write_text("COZE_CN_API_TOKEN=test-secret\nCOZE_CN_API_TOKEN=other-secret\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 2") as error:
                CHECK.read_config(path)
            self.assertNotIn("secret", str(error.exception))

    def response(self, workspaces, total):
        response = io.StringIO(json.dumps({"code": 0, "data": {"workspaces": workspaces, "total_count": total}}))
        response.status = 200
        return response

    def test_pagination_and_redaction(self):
        opener = Mock()
        opener.open.side_effect = [self.response([{"id": str(i)} for i in range(50)], 51),
                                   self.response([{"id": "example-workspace", "role_type": "owner", "name": "private-name"}], 51)]
        result = CHECK.verify_workspace(self.config, opener)
        self.assertTrue(result["verified"])
        self.assertEqual(result["role"], "owner")
        self.assertEqual(opener.open.call_count, 2)
        for private in ("example-workspace", "private-name", "test-secret"):
            self.assertNotIn(private, json.dumps(result))

    def test_http_and_business_errors_are_redacted(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://api.coze.cn", 403, "test-secret", {}, None)
        result = CHECK.verify_workspace(self.config, opener)
        self.assertFalse(result["verified"])
        self.assertNotIn("test-secret", json.dumps(result))
        opener.open.side_effect = None
        response = io.StringIO(json.dumps({"code": 123, "msg": "test-secret"}))
        response.status = 200
        opener.open.return_value = response
        result = CHECK.verify_workspace(self.config, opener)
        self.assertEqual(result["reason"], "business_error")
        self.assertNotIn("test-secret", json.dumps(result))

    def test_redirects_are_not_followed(self):
        handler = CHECK.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://elsewhere.example"))

    def test_curl_keeps_token_out_of_arguments_and_verifies_tls(self):
        request = CHECK.urllib.request.Request("https://api.coze.com/v1/workspaces",
                                               headers={"Authorization": "Bearer test-secret"})
        with patch.object(CHECK.subprocess, "run", return_value=Mock(returncode=0, stdout='{"code": 0}\n200')) as run:
            with CHECK.CurlOpener().open(request, 20) as response:
                self.assertEqual(response.status, 200)
            args = run.call_args.args[0]
            self.assertNotIn("test-secret", " ".join(args))
            self.assertNotIn("--insecure", args)
            self.assertNotIn("--location", args)
            self.assertIn("--disable", args)
            self.assertIn("test-secret", run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
