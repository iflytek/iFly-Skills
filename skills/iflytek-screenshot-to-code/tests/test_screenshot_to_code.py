import importlib.util
import io
import json
import os
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_to_code.py"
SPEC = importlib.util.spec_from_file_location("screenshot_to_code", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
screenshot_to_code = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(screenshot_to_code)


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, amount=-1):
        return self.body[:amount] if amount >= 0 else self.body


class ScreenshotToCodeTests(unittest.TestCase):
    def test_image_data_url_validates_png_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "screen.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

            result = screenshot_to_code.image_data_url(image)

        self.assertTrue(result.startswith("data:image/png;base64,"))

    def test_image_data_url_rejects_extension_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "screen.png"
            image.write_bytes(b"not a png")

            with self.assertRaisesRegex(
                screenshot_to_code.ScreenshotToCodeError,
                "do not match",
            ):
                screenshot_to_code.image_data_url(image)

    def test_completion_endpoint_accepts_base_or_full_endpoint(self):
        base = "https://example.test/v2/"
        full = "https://example.test/v2/chat/completions"

        self.assertEqual(
            screenshot_to_code.completion_endpoint(base),
            full,
        )
        self.assertEqual(
            screenshot_to_code.completion_endpoint(full),
            full,
        )

    def test_completion_endpoint_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(
            screenshot_to_code.ScreenshotToCodeError,
            "must not contain credentials",
        ):
            screenshot_to_code.completion_endpoint("https://key@example.test/v2")

    def test_request_payload_contains_image_and_stack_contract(self):
        payload = screenshot_to_code.request_payload(
            model="vision-model",
            stack="react-tailwind",
            data_url="data:image/png;base64,abc",
            extra_instructions="Make the primary button interactive.",
            temperature=0.1,
            max_tokens=4096,
        )

        self.assertEqual(payload["model"], "vision-model")
        self.assertFalse(payload["stream"])
        content = payload["messages"][0]["content"]
        self.assertIn("exports a default React component", content[0]["text"])
        self.assertIn("primary button interactive", content[0]["text"])
        self.assertEqual(
            content[1]["image_url"]["url"],
            "data:image/png;base64,abc",
        )

    def test_call_maas_builds_authenticated_json_request(self):
        response_body = json.dumps(
            {"choices": [{"message": {"content": "<html></html>"}}]}
        ).encode()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(response_body)

        with patch.object(screenshot_to_code, "urlopen", fake_urlopen):
            result = screenshot_to_code.call_maas(
                "https://example.test/v2/chat/completions",
                "test-key",
                {"model": "vision-model"},
                12.0,
            )

        request = captured["request"]
        self.assertEqual(captured["timeout"], 12.0)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(request.data), {"model": "vision-model"})
        self.assertEqual(result["choices"][0]["message"]["content"], "<html></html>")

    def test_call_maas_redacts_api_errors_before_truncating(self):
        api_key = "synthetic-credential-not-for-network-use"
        message = "x" * 470 + f" Invalid API key {api_key}; Bearer {api_key}"
        errors = [
            {"error": {"message": message}},
            {"error": message},
            {"message": message},
        ]
        for error in errors:
            for raises_http_error in (False, True):
                with self.subTest(error=error, raises_http_error=raises_http_error):
                    body = json.dumps(error).encode()
                    if raises_http_error:
                        response = patch.object(
                            screenshot_to_code,
                            "urlopen",
                            side_effect=HTTPError(
                                "https://example.test/v2/chat/completions",
                                401,
                                f"Unauthorized: {api_key}",
                                {"Authorization": f"Bearer {api_key}"},
                                io.BytesIO(body),
                            ),
                        )
                    else:
                        response = patch.object(
                            screenshot_to_code,
                            "urlopen",
                            return_value=FakeResponse(body, status=401),
                        )
                    with response, self.assertRaises(
                        screenshot_to_code.ScreenshotToCodeError
                    ) as raised:
                        screenshot_to_code.call_maas(
                            "https://example.test/v2/chat/completions", api_key, {}, 1
                        )
                    rendered = "".join(traceback.format_exception(raised.exception))
                    self.assertIn("HTTP 401", rendered)
                    self.assertIn("[REDACTED]", rendered)
                    self.assertNotIn(api_key[:8], rendered)
                    self.assertLessEqual(
                        len(str(raised.exception)),
                        len("Astron MaaS returned HTTP 401: ") + 500,
                    )

    def test_call_maas_redacts_transport_errors_and_their_context(self):
        api_key = "synthetic-credential-not-for-network-use"
        errors = [
            URLError(f"Connection failed with Authorization: Bearer {api_key}"),
            TimeoutError(f"Timed out for {api_key}"),
            OSError(f"Connection reset with {api_key}"),
            ValueError(f"Invalid header value: Bearer {api_key}"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(
                    screenshot_to_code, "urlopen", side_effect=error
                ), self.assertRaises(screenshot_to_code.ScreenshotToCodeError) as raised:
                    screenshot_to_code.call_maas(
                        "https://example.test/v2/chat/completions", api_key, {}, 1
                    )
                rendered = "".join(traceback.format_exception(raised.exception))
                self.assertNotIn(api_key, rendered)
                if not isinstance(error, TimeoutError):
                    self.assertIn("[REDACTED]", rendered)

    def test_call_maas_keeps_http_status_if_error_body_read_fails(self):
        api_key = "synthetic-credential-not-for-network-use"
        error = HTTPError(
            "https://example.test/v2/chat/completions", 401, api_key, {}, None
        )
        with patch.object(
            screenshot_to_code, "urlopen", side_effect=error
        ), patch.object(
            error, "read", side_effect=OSError(api_key)
        ), self.assertRaises(screenshot_to_code.ScreenshotToCodeError) as raised:
            screenshot_to_code.call_maas(
                "https://example.test/v2/chat/completions", api_key, {}, 1
            )
        self.assertEqual(str(raised.exception), "Astron MaaS returned HTTP 401")
        self.assertNotIn(api_key, "".join(traceback.format_exception(raised.exception)))

    def test_call_maas_rejects_line_breaks_in_api_key_before_network(self):
        for api_key in ("synthetic-key\nextra", "synthetic-key\rextra"):
            with self.subTest(api_key=api_key):
                with patch.object(screenshot_to_code, "urlopen") as transport:
                    with self.assertRaisesRegex(
                        screenshot_to_code.ScreenshotToCodeError, "line breaks"
                    ) as raised:
                        screenshot_to_code.call_maas(
                            "https://example.test/v2/chat/completions", api_key, {}, 1
                        )
                transport.assert_not_called()
                self.assertNotIn("synthetic-key", str(raised.exception))

    def test_response_text_supports_text_parts(self):
        result = screenshot_to_code.response_text(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "first"},
                                {"type": "output_text", "text": " second"},
                            ]
                        }
                    }
                ]
            }
        )

        self.assertEqual(result, "first second")

    def test_normalize_code_unwraps_one_exact_fence(self):
        for fence in ("```", "~~~"):
            for newline in ("\n", "\r\n"):
                with self.subTest(fence=fence, newline=newline):
                    result = screenshot_to_code.normalize_code(
                        f"{fence}html{newline}<!doctype html><html></html>{newline}{fence}"
                    )
                    self.assertEqual(result, "<!doctype html><html></html>")

    def test_normalize_code_rejects_prose_around_fence(self):
        with self.assertRaisesRegex(
            screenshot_to_code.ScreenshotToCodeError,
            "mixed prose",
        ):
            screenshot_to_code.normalize_code(
                "Here is the code:\n```html\n<html></html>\n```"
            )

    def test_normalize_code_rejects_multiple_and_nested_fences(self):
        outputs = [
            "```html\n<html></html>\n```\n```css\nbody {}\n```",
            "```html\n<html>\n```css\nbody {}\n```\n</html>\n```",
            "~~~html\n<html></html>\n~~~\n~~~css\nbody {}\n~~~",
            "~~~html\n<html>\n~~~css\nbody {}\n~~~\n</html>\n~~~",
            "```html\n<html>\n  ~~~css\nbody {}\n  ~~~\n</html>\n```",
            "~~~html\n<html></html>\n~~~\n```css\nbody {}\n```",
            "```html\r\n<html></html>\r\n```\r\n```css\r\nbody {}\r\n```",
        ]
        for output in outputs:
            with self.subTest(output=output):
                with self.assertRaises(screenshot_to_code.ScreenshotToCodeError):
                    screenshot_to_code.normalize_code(output)

    def test_validate_code_enforces_stack_contracts(self):
        screenshot_to_code.validate_code("<html><body></body></html>", "html-css")
        screenshot_to_code.validate_code(
            "const App = () => <main />; export default App;",
            "react-tailwind",
        )
        screenshot_to_code.validate_code(
            "<template><main /></template><script setup></script>",
            "vue-tailwind",
        )

        with self.assertRaises(screenshot_to_code.ScreenshotToCodeError):
            screenshot_to_code.validate_code("<main>fragment</main>", "html-css")

    def test_write_code_is_atomic_and_does_not_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "generated.html"
            screenshot_to_code.write_code(
                output,
                "<html><body>first</body></html>",
                "html-css",
                force=False,
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "<html><body>first</body></html>\n",
            )

            with self.assertRaisesRegex(
                screenshot_to_code.ScreenshotToCodeError,
                "already exists",
            ):
                screenshot_to_code.write_code(
                    output,
                    "<html><body>second</body></html>",
                    "html-css",
                    force=False,
                )

            screenshot_to_code.write_code(
                output,
                "<html><body>second</body></html>",
                "html-css",
                force=True,
            )
            self.assertIn("second", output.read_text(encoding="utf-8"))

    def test_main_rejects_extra_fences_without_creating_or_replacing_output(self):
        outputs = [
            "```html\n<html></html>\n```\n```css\nbody {}\n```",
            "```html\n<html>\n```css\nbody {}\n```\n</html>\n```",
            "~~~html\n<html></html>\n~~~\n~~~css\nbody {}\n~~~",
            "~~~html\n<html>\n~~~css\nbody {}\n~~~\n</html>\n~~~",
            "```html\n<html>\n  ~~~css\nbody {}\n  ~~~\n</html>\n```",
            "~~~html\n<html></html>\n~~~\n```css\nbody {}\n```",
        ]
        for content in outputs:
            for existing in (False, True):
                with self.subTest(content=content, existing=existing):
                    with tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        image = root / "screen.png"
                        output = root / "generated" / "screen.html"
                        image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
                        if existing:
                            output.parent.mkdir()
                            output.write_bytes(b"existing output")
                        response = {"choices": [{"message": {"content": content}}]}
                        stderr = io.StringIO()
                        with patch.dict(os.environ, {
                            "IFLYTEK_MAAS_API_KEY": "test-key",
                            "IFLYTEK_MAAS_MODEL_ID": "vision-model",
                        }), patch.object(
                            screenshot_to_code, "call_maas", return_value=response
                        ), patch("sys.stderr", stderr):
                            exit_code = screenshot_to_code.main(
                                [str(image), "--output", str(output), "--force"]
                            )
                        self.assertEqual(exit_code, 1)
                        self.assertIn("no output file was written", stderr.getvalue())
                        if existing:
                            self.assertEqual(output.read_bytes(), b"existing output")
                            self.assertEqual(list(output.parent.iterdir()), [output])
                        else:
                            self.assertFalse(output.parent.exists())

    def test_main_redacts_error_messages_and_preserves_existing_output(self):
        api_key = "synthetic-credential-not-for-network-use"
        errors = [
            screenshot_to_code.ScreenshotToCodeError(f"Server echoed {api_key}"),
            OSError(f"Could not read {api_key}"),
            ValueError(f"Invalid value {api_key}"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    image = root / "screen.png"
                    output = root / "screen.html"
                    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
                    output.write_bytes(b"existing output")
                    stderr = io.StringIO()
                    with patch.dict(os.environ, {
                        "IFLYTEK_MAAS_API_KEY": api_key,
                        "IFLYTEK_MAAS_MODEL_ID": "vision-model",
                    }), patch.object(
                        screenshot_to_code, "call_maas", side_effect=error
                    ), patch("sys.stderr", stderr):
                        exit_code = screenshot_to_code.main(
                            [str(image), "--output", str(output), "--force"]
                        )
                    self.assertEqual(exit_code, 1)
                    self.assertNotIn(api_key, stderr.getvalue())
                    self.assertIn("[REDACTED]", stderr.getvalue())
                    self.assertEqual(output.read_bytes(), b"existing output")

    def test_main_redacts_remote_api_error_without_creating_output(self):
        api_key = "synthetic-credential-not-for-network-use"
        body = json.dumps({"error": {"message": f"Invalid key {api_key}"}}).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "screen.png"
            output = root / "generated" / "screen.html"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            error = HTTPError(
                "https://example.test/v2/chat/completions", 401, api_key,
                {"Authorization": f"Bearer {api_key}"}, io.BytesIO(body),
            )
            stderr = io.StringIO()
            with patch.dict(os.environ, {
                "IFLYTEK_MAAS_API_KEY": api_key,
                "IFLYTEK_MAAS_MODEL_ID": "vision-model",
            }), patch.object(
                screenshot_to_code, "urlopen", side_effect=error
            ), patch("sys.stderr", stderr):
                exit_code = screenshot_to_code.main([str(image), "--output", str(output)])
            self.assertEqual(exit_code, 1)
            self.assertIn("HTTP 401: Invalid key [REDACTED]", stderr.getvalue())
            self.assertNotIn(api_key, stderr.getvalue())
            self.assertFalse(output.parent.exists())

    def test_main_writes_validated_output_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "screen.png"
            output = root / "screen.html"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            response = {
                "choices": [
                    {
                        "message": {
                            "content": "<!doctype html><html><body>ok</body></html>"
                        }
                    }
                ]
            }

            with patch.dict(
                os.environ,
                {
                    "IFLYTEK_MAAS_API_KEY": "test-key",
                    "IFLYTEK_MAAS_MODEL_ID": "vision-model",
                },
                clear=False,
            ), patch.object(screenshot_to_code, "call_maas", return_value=response):
                exit_code = screenshot_to_code.main(
                    [str(image), "--output", str(output)]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("<body>ok</body>", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
