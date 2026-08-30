import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
        result = screenshot_to_code.normalize_code(
            "```html\n<!doctype html><html></html>\n```"
        )

        self.assertEqual(result, "<!doctype html><html></html>")

    def test_normalize_code_rejects_prose_around_fence(self):
        with self.assertRaisesRegex(
            screenshot_to_code.ScreenshotToCodeError,
            "mixed code fences with prose",
        ):
            screenshot_to_code.normalize_code(
                "Here is the code:\n```html\n<html></html>\n```"
            )

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
