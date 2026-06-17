#!/usr/bin/env python3
"""iFlytek Image Understanding API (图片理解).

Analyze images using iFlytek Spark Vision model. Supports single-turn and
multi-turn conversations about image content.

Environment variables:
    IFLY_APP_ID      - Required. App ID from https://console.xfyun.cn
    IFLY_API_KEY     - Required. API Key
    IFLY_API_SECRET  - Required. API Secret

Usage:
    # Describe an image
    python image_understanding.py photo.jpg

    # Ask a question about an image
    python image_understanding.py photo.jpg --question "图片里有什么动物？"

    # Use basic model (lower token cost)
    python image_understanding.py photo.jpg --domain general

    # Output raw JSON frames
    python image_understanding.py photo.jpg --raw

Examples:
    python image_understanding.py cat.jpg -q "这只猫是什么品种？"
    python image_understanding.py receipt.png -q "总金额是多少？"
    python image_understanding.py scene.jpg --domain general
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import ssl
import socket
import struct
import sys
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

WS_URL = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"


def build_auth_url(ws_url: str, api_key: str, api_secret: str) -> str:
    """Build HMAC-SHA256 signed WebSocket URL."""
    url_result = urlparse(ws_url)
    date = format_date_time(mktime(datetime.now().timetuple()))

    signature_origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(
        url_result.hostname, date, url_result.path
    )
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature_sha).decode("utf-8")

    authorization_origin = (
        'api_key="%s", algorithm="%s", headers="%s", signature="%s"'
        % (api_key, "hmac-sha256", "host date request-line", signature_b64)
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    params = {
        "authorization": authorization,
        "date": date,
        "host": url_result.hostname,
    }
    return ws_url + "?" + urlencode(params)


def read_image_base64(image_path: str) -> str:
    """Read image file and return base64 string."""
    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}", file=sys.stderr)
        sys.exit(1)
    size = os.path.getsize(image_path)
    if size > 4 * 1024 * 1024:
        print(f"Error: Image too large ({size} bytes). Max 4MB.", file=sys.stderr)
        sys.exit(1)
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def gen_params(app_id: str, messages: list, domain: str,
               temperature: float, max_tokens: int) -> dict:
    """Generate request parameters."""
    return {
        "header": {
            "app_id": app_id,
        },
        "parameter": {
            "chat": {
                "domain": domain,
                "temperature": temperature,
                "top_k": 4,
                "max_tokens": max_tokens,
                "auditing": "default",
            }
        },
        "payload": {
            "message": {
                "text": messages,
            }
        },
    }


# ── Minimal WebSocket client (stdlib only) ──────────────────────────────

def _ws_handshake(sock, host, path_with_query):
    """Perform WebSocket upgrade handshake."""
    import secrets
    key = base64.b64encode(secrets.token_bytes(16)).decode()
    lines = [
        f"GET {path_with_query} HTTP/1.1",
        f"Host: {host}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
        "",
        "",
    ]
    sock.sendall("\r\n".join(lines).encode("utf-8"))

    # Read HTTP response headers
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("WebSocket handshake failed: connection closed")
        buf += chunk

    header_part = buf.split(b"\r\n\r\n")[0].decode("utf-8", errors="replace")
    status_line = header_part.split("\r\n")[0]
    if "101" not in status_line:
        raise ConnectionError(f"WebSocket handshake failed: {status_line}")

    # Return any leftover data after headers
    return buf.split(b"\r\n\r\n", 1)[1]


def _ws_send(sock, data: str):
    """Send a text frame over WebSocket (client must mask)."""
    import secrets
    payload = data.encode("utf-8")
    frame = bytearray()
    frame.append(0x81)  # FIN + text opcode

    length = len(payload)
    if length < 126:
        frame.append(0x80 | length)  # MASK bit set
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", length))

    mask = secrets.token_bytes(4)
    frame.extend(mask)
    masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
    frame.extend(masked)
    sock.sendall(bytes(frame))


def _ws_recv_frame(sock, leftover: bytearray) -> tuple:
    """Receive one WebSocket frame. Returns (opcode, payload, leftover)."""

    def _read_exact(n):
        nonlocal leftover
        while len(leftover) < n:
            chunk = sock.recv(8192)
            if not chunk:
                raise ConnectionError("Connection closed while reading frame")
            leftover.extend(chunk)
        data = bytes(leftover[:n])
        leftover = leftover[n:]
        return data

    hdr = _read_exact(2)
    opcode = hdr[0] & 0x0F
    masked = bool(hdr[1] & 0x80)
    length = hdr[1] & 0x7F

    if length == 126:
        length = struct.unpack(">H", _read_exact(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _read_exact(8))[0]

    if masked:
        mask = _read_exact(4)
        raw = _read_exact(length)
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
    else:
        payload = _read_exact(length)

    return opcode, payload, leftover


def _ws_close(sock):
    """Send WebSocket close frame."""
    try:
        import secrets
        frame = bytearray([0x88, 0x82])  # FIN + close, masked, 2 bytes payload
        mask = secrets.token_bytes(4)
        frame.extend(mask)
        # Close code 1000 (normal)
        close_payload = struct.pack(">H", 1000)
        masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(close_payload))
        frame.extend(masked)
        sock.sendall(bytes(frame))
    except Exception:
        pass


def ws_communicate(url: str, message: str) -> list:
    """Connect to WebSocket, send message, collect all response frames."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    path_query = parsed.path
    if parsed.query:
        path_query += "?" + parsed.query

    raw_sock = socket.create_connection((host, port), timeout=60)

    if parsed.scheme == "wss":
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(raw_sock, server_hostname=host)
    else:
        sock = raw_sock

    try:
        leftover_data = _ws_handshake(sock, host, path_query)
        leftover = bytearray(leftover_data)

        _ws_send(sock, message)

        frames = []
        while True:
            opcode, payload, leftover = _ws_recv_frame(sock, leftover)

            if opcode == 0x1:  # text frame
                frames.append(payload.decode("utf-8"))
            elif opcode == 0x8:  # close
                break
            elif opcode == 0x9:  # ping → pong
                _ws_send(sock, "")  # simplified pong
                continue

            # Check if this is the last frame from the API
            try:
                data = json.loads(payload.decode("utf-8"))
                header = data.get("header", {})
                if header.get("code", 0) != 0:
                    break
                choices = data.get("payload", {}).get("choices", {})
                if choices.get("status") == 2:
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        _ws_close(sock)
        return frames
    finally:
        sock.close()


def run_understanding(app_id: str, api_key: str, api_secret: str,
                      messages: list, domain: str, temperature: float,
                      max_tokens: int, raw: bool) -> str:
    """Run image understanding and return the assembled text response."""
    auth_url = build_auth_url(WS_URL, api_key, api_secret)
    params = gen_params(app_id, messages, domain, temperature, max_tokens)
    request_data = json.dumps(params)

    frames = ws_communicate(auth_url, request_data)

    if raw:
        for f in frames:
            print(f)
        return ""

    full_text = ""
    for f in frames:
        try:
            data = json.loads(f)
        except json.JSONDecodeError:
            continue

        header = data.get("header", {})
        code = header.get("code", 0)
        if code != 0:
            msg = header.get("message", "unknown error")
            print(f"Error (code {code}): {msg}", file=sys.stderr)
            if raw:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            sys.exit(1)

        choices = data.get("payload", {}).get("choices", {})
        texts = choices.get("text", [])
        for t in texts:
            content = t.get("content", "")
            full_text += content

        # Print usage info on last frame
        if choices.get("status") == 2:
            usage = data.get("payload", {}).get("usage", {}).get("text", {})
            if usage:
                print(
                    f"\n--- Token usage: prompt={usage.get('prompt_tokens', '?')}, "
                    f"completion={usage.get('completion_tokens', '?')}, "
                    f"total={usage.get('total_tokens', '?')} ---",
                    file=sys.stderr,
                )

    return full_text


def main():
    parser = argparse.ArgumentParser(
        description="iFlytek Image Understanding (图片理解)"
    )
    parser.add_argument("image", help="Image file path (.jpg, .jpeg, .png)")
    parser.add_argument(
        "--question", "-q", default="请详细描述这张图片的内容",
        help="Question about the image (default: describe the image)"
    )
    parser.add_argument(
        "--domain", "-d", default="imagev3",
        choices=["general", "imagev3"],
        help="Model version: general (basic, fixed 273 tokens/image) or imagev3 (advanced, dynamic tokens). Default: imagev3"
    )
    parser.add_argument(
        "--temperature", "-t", type=float, default=0.5,
        help="Sampling temperature (0, 1]. Default: 0.5"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=2048,
        help="Max response tokens (1-8192). Default: 2048"
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="Output raw WebSocket JSON frames"
    )
    args = parser.parse_args()

    # Read credentials
    app_id = os.environ.get("IFLY_APP_ID")
    api_key = os.environ.get("IFLY_API_KEY")
    api_secret = os.environ.get("IFLY_API_SECRET")

    if not all([app_id, api_key, api_secret]):
        missing = []
        if not app_id:
            missing.append("IFLY_APP_ID")
        if not api_key:
            missing.append("IFLY_API_KEY")
        if not api_secret:
            missing.append("IFLY_API_SECRET")
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Get credentials from https://console.xfyun.cn", file=sys.stderr)
        sys.exit(1)

    # Build messages: image first, then question
    image_b64 = read_image_base64(args.image)
    messages = [
        {"role": "user", "content": image_b64, "content_type": "image"},
        {"role": "user", "content": args.question, "content_type": "text"},
    ]

    result = run_understanding(
        app_id, api_key, api_secret,
        messages=messages,
        domain=args.domain,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        raw=args.raw,
    )

    if result:
        print(result)


if __name__ == "__main__":
    main()
