#!/usr/bin/env python3
"""Generate frontend code from a screenshot with an Astron MaaS vision model.

The client uses only the Python standard library and the OpenAI-compatible
Astron MaaS chat completions endpoint.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_ERROR_BODY_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

STACKS = {
    "html-css": {
        "extension": ".html",
        "contract": (
            "Return one complete HTML document with semantic HTML and all CSS "
            "inside a <style> element. Do not require a build step."
        ),
    },
    "react-tailwind": {
        "extension": ".jsx",
        "contract": (
            "Return one JSX module that exports a default React component and "
            "uses Tailwind utility classes. Do not include package manifests or "
            "additional files."
        ),
    },
    "vue-tailwind": {
        "extension": ".vue",
        "contract": (
            "Return one Vue single-file component with <template> and <script "
            "setup> sections and Tailwind utility classes. Do not include package "
            "manifests or additional files."
        ),
    },
}


class ScreenshotToCodeError(RuntimeError):
    """A safe, user-facing error from the screenshot-to-code workflow."""


def _bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def _bounded_float(minimum: float, maximum: float):
    def parse(value: str) -> float:
        try:
            parsed = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a number") from exc
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def _image_mime_type(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if suffix in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        suffix == ".webp"
        and len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
    ):
        return "image/webp"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ScreenshotToCodeError(
            "Unsupported image type. Use PNG, JPEG, or WebP."
        )
    raise ScreenshotToCodeError(
        f"The file contents do not match the {suffix} extension."
    )


def image_data_url(image_path: Path) -> str:
    """Validate an image and return an RFC 2397 base64 data URL."""
    if not image_path.is_file():
        raise ScreenshotToCodeError(f"Screenshot not found: {image_path}")
    size = image_path.stat().st_size
    if size == 0:
        raise ScreenshotToCodeError("Screenshot is empty.")
    if size > MAX_IMAGE_BYTES:
        raise ScreenshotToCodeError(
            f"Screenshot is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MiB."
        )
    data = image_path.read_bytes()
    mime_type = _image_mime_type(image_path, data)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def completion_endpoint(base_url: str) -> str:
    """Normalize a MaaS base URL into a chat completions endpoint."""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ScreenshotToCodeError("MaaS base URL must be an HTTP(S) URL.")
    if parsed.username or parsed.password:
        raise ScreenshotToCodeError("MaaS base URL must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise ScreenshotToCodeError("MaaS base URL must not contain a query or fragment.")

    path = parsed.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path += "/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def generation_prompt(stack: str, extra_instructions: str | None = None) -> str:
    """Build the screenshot reconstruction prompt for one output stack."""
    stack_contract = STACKS[stack]["contract"]
    prompt = f"""Recreate the attached interface screenshot as working frontend code.

Output contract:
- {stack_contract}
- Return code only. Do not use Markdown fences or explanatory prose.

Fidelity requirements:
- Match visible layout, spacing, typography, colors, borders, and responsive structure.
- Preserve all legible text exactly; do not invent sections or content not shown.
- Use semantic, accessible markup and sensible focus/alt text where applicable.
- Reproduce repeated elements as data-driven components when the selected stack supports it.
- Do not embed the screenshot itself or use it as a page background.
- Prefer CSS shapes, gradients, and inline SVG for simple visual details. Use clear
  placeholders only when a source asset cannot be reconstructed from the screenshot.
"""
    if extra_instructions:
        normalized = extra_instructions.strip()
        if len(normalized) > 4000:
            raise ScreenshotToCodeError(
                "Extra instructions must be 4000 characters or fewer."
            )
        if normalized:
            prompt += f"\nAdditional user requirements:\n{normalized}\n"
    return prompt


def request_payload(
    model: str,
    stack: str,
    data_url: str,
    extra_instructions: str | None,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": generation_prompt(stack, extra_instructions)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _safe_api_error(body: bytes, status: int) -> str:
    message = ""
    try:
        parsed = json.loads(body.decode("utf-8"))
        error = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            message = error["message"].strip()
        elif isinstance(error, str):
            message = error.strip()
        elif isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
            message = parsed["message"].strip()
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    suffix = f": {message[:500]}" if message else ""
    return f"Astron MaaS returned HTTP {status}{suffix}"


def call_maas(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Call the non-streaming OpenAI-compatible MaaS endpoint."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "iflytek-screenshot-to-code/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ScreenshotToCodeError("Astron MaaS response is too large.")
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        raw_error = exc.read(MAX_ERROR_BODY_BYTES)
        raise ScreenshotToCodeError(_safe_api_error(raw_error, exc.code)) from exc
    except URLError as exc:
        reason = getattr(exc, "reason", "connection failed")
        raise ScreenshotToCodeError(f"Could not reach Astron MaaS: {reason}") from exc
    except TimeoutError as exc:
        raise ScreenshotToCodeError("Astron MaaS request timed out.") from exc

    if status >= 400:
        raise ScreenshotToCodeError(_safe_api_error(raw, status))
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScreenshotToCodeError("Astron MaaS returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ScreenshotToCodeError("Astron MaaS returned an unexpected response shape.")
    return parsed


def response_text(response: dict[str, Any]) -> str:
    """Extract assistant text from an OpenAI-compatible completion response."""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ScreenshotToCodeError("Astron MaaS response has no choices.")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and part.get("type") in {None, "text", "output_text"}:
                parts.append(text)
        if parts:
            return "".join(parts)
    raise ScreenshotToCodeError("Astron MaaS response has no text content.")


def normalize_code(model_output: str) -> str:
    """Accept raw code or one exact Markdown code block, rejecting mixed prose."""
    stripped = model_output.strip()
    if not stripped:
        raise ScreenshotToCodeError("Astron MaaS returned empty code.")
    fenced = re.fullmatch(
        r"```[A-Za-z0-9_.+-]*[ \t]*\r?\n(?P<code>.*)\r?\n```",
        stripped,
        flags=re.DOTALL,
    )
    if fenced:
        stripped = fenced.group("code").strip()
    elif "```" in stripped:
        raise ScreenshotToCodeError(
            "Model response mixed code fences with prose; no output file was written."
        )
    if not stripped or "\x00" in stripped:
        raise ScreenshotToCodeError("Astron MaaS returned invalid code.")
    return stripped


def validate_code(code: str, stack: str) -> None:
    """Check the minimum single-file contract before writing model output."""
    lowered = code.lower()
    if stack == "html-css":
        if "<html" not in lowered or "</html>" not in lowered:
            raise ScreenshotToCodeError(
                "Generated HTML is not a complete document; no output file was written."
            )
    elif stack == "react-tailwind":
        if not re.search(r"\bexport\s+default\b", code):
            raise ScreenshotToCodeError(
                "Generated React code has no default export; no output file was written."
            )
    elif stack == "vue-tailwind":
        if "<template" not in lowered or "<script" not in lowered:
            raise ScreenshotToCodeError(
                "Generated Vue code is not a single-file component; no output file was written."
            )


def write_code(path: Path, code: str, stack: str, force: bool) -> None:
    """Atomically write validated code without overwriting by default."""
    expected_extension = STACKS[stack]["extension"]
    if path.suffix.lower() != expected_extension:
        raise ScreenshotToCodeError(
            f"Output for {stack} must use the {expected_extension} extension."
        )
    if path.exists() and not force:
        raise ScreenshotToCodeError(
            f"Output already exists: {path}. Pass --force to replace it."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(code)
            temporary.write("\n")
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise ScreenshotToCodeError(f"Could not write output: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate frontend code from a screenshot with Astron MaaS."
    )
    parser.add_argument("image", type=Path, help="PNG, JPEG, or WebP screenshot")
    parser.add_argument(
        "--stack",
        choices=sorted(STACKS),
        default="html-css",
        help="Output stack (default: html-css)",
    )
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument(
        "--instructions",
        help="Extra fidelity or interaction requirements for the generated UI",
    )
    parser.add_argument(
        "--model",
        help="Astron MaaS vision model ID (or set IFLYTEK_MAAS_MODEL_ID)",
    )
    parser.add_argument(
        "--base-url",
        help=f"Astron MaaS API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--temperature",
        type=_bounded_float(0.0, 1.0),
        default=0.1,
    )
    parser.add_argument(
        "--max-tokens",
        type=_bounded_int(1, 8192),
        default=8192,
    )
    parser.add_argument("--timeout", type=_bounded_float(1.0, 600.0), default=180.0)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api_key = os.environ.get("IFLYTEK_MAAS_API_KEY", "").strip()
    model = (args.model or os.environ.get("IFLYTEK_MAAS_MODEL_ID", "")).strip()
    base_url = (
        args.base_url
        or os.environ.get("IFLYTEK_MAAS_BASE_URL")
        or DEFAULT_BASE_URL
    )
    if not api_key:
        parser.error("set IFLYTEK_MAAS_API_KEY before running this command")
    if not model:
        parser.error("pass --model or set IFLYTEK_MAAS_MODEL_ID")

    try:
        data_url = image_data_url(args.image)
        endpoint = completion_endpoint(base_url)
        payload = request_payload(
            model=model,
            stack=args.stack,
            data_url=data_url,
            extra_instructions=args.instructions,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        response = call_maas(endpoint, api_key, payload, args.timeout)
        code = normalize_code(response_text(response))
        validate_code(code, args.stack)
        write_code(args.output, code, args.stack, args.force)
    except ScreenshotToCodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.stack} code to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
