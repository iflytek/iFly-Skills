#!/usr/bin/env python3
"""iFlytek Voice Clone (声音复刻) — train a custom voice and synthesize speech.

Two workflows:
  1. TRAIN  — upload audio samples → train a voice model → get res_id
  2. SYNTH  — use res_id to synthesize speech with the cloned voice

Environment variables:
    IFLY_APP_ID      - Required. App ID from https://console.xfyun.cn
    IFLY_API_KEY     - Required. API Key (used for both training auth and TTS WebSocket auth)
    IFLY_API_SECRET  - Required. API Secret (used for TTS WebSocket auth)

Training workflow:
    python voiceclone.py train get-text                     # Get training text list
    python voiceclone.py train create --name "MyVoice" --sex male --engine omni_v1
    python voiceclone.py train upload --task-id 12345 --audio voice.wav --text-id 5001 --seg-id 1
    python voiceclone.py train submit --task-id 12345
    python voiceclone.py train status --task-id 12345       # Poll until done → get res_id

Synthesis:
    python voiceclone.py synth "你好" --res-id xxx --output hello.mp3
    python voiceclone.py synth --file article.txt --res-id xxx -o article.mp3
    echo "测试" | python voiceclone.py synth --res-id xxx

Quick one-shot train (upload local file + auto-submit):
    python voiceclone.py train quick --audio voice.wav --name "MyVoice" \\
        --sex female --text-id 5001 --seg-id 1 --wait
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import ssl
import struct
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time

# ─── Constants ────────────────────────────────────────────────────────────────

TRAIN_BASE_URL = "http://opentrain.xfyousheng.com/voice_train"
AUTH_TOKEN_URL = "http://avatar-hci.xfyousheng.com/aiauth/v1/token"
TTS_WS_URL = "wss://cn-huabei-1.xf-yun.com/v1/private/voice_clone"
DEFAULT_VCN = "x6_clone"


# ─── Minimal WebSocket client (stdlib only) ───────────────────────────────────

class SimpleWebSocket:
    """Bare-bones RFC 6455 WebSocket client using only stdlib."""

    def __init__(self, url, on_message=None, on_error=None, on_close=None, on_open=None):
        self.url = url
        self.on_message = on_message or (lambda ws, msg: None)
        self.on_error = on_error or (lambda ws, err: None)
        self.on_close = on_close or (lambda ws: None)
        self.on_open = on_open or (lambda ws: None)
        self._sock = None
        self._closed = False

    def connect(self):
        """Connect and run the message loop."""
        parsed = urllib.parse.urlparse(self.url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path
        if parsed.query:
            path += "?" + parsed.query

        import socket
        raw = socket.create_connection((host, port), timeout=30)
        if parsed.scheme == "wss":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._sock = ctx.wrap_socket(raw, server_hostname=host)
        else:
            self._sock = raw

        # WebSocket handshake
        ws_key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self._sock.sendall(handshake.encode())

        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed during handshake")
            resp += chunk

        status_line = resp.split(b"\r\n")[0].decode()
        if "101" not in status_line:
            raise ConnectionError(f"WebSocket handshake failed: {status_line}")

        try:
            self.on_open(self)
        except Exception as e:
            self.on_error(self, e)
            return

        while not self._closed:
            try:
                msg = self._recv_frame()
                if msg is None:
                    break
                self.on_message(self, msg)
            except Exception as e:
                if not self._closed:
                    self.on_error(self, e)
                break

        self.on_close(self)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._send_frame(data, opcode=0x1)

    def close(self):
        self._closed = True
        try:
            self._send_frame(b"", opcode=0x8)
        except Exception:
            pass
        try:
            self._sock.close()
        except Exception:
            pass

    def _send_frame(self, data, opcode=0x1):
        length = len(data)
        header = bytearray()
        header.append(0x80 | opcode)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytearray(data)
        for i in range(len(masked)):
            masked[i] ^= mask[i % 4]
        self._sock.sendall(bytes(header) + bytes(masked))

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv_frame(self):
        head = self._recv_exact(2)
        if head is None:
            return None
        opcode = head[0] & 0x0F
        masked = (head[1] & 0x80) != 0
        length = head[1] & 0x7F
        if length == 126:
            raw = self._recv_exact(2)
            if raw is None:
                return None
            length = struct.unpack("!H", raw)[0]
        elif length == 127:
            raw = self._recv_exact(8)
            if raw is None:
                return None
            length = struct.unpack("!Q", raw)[0]
        if masked:
            mask_bytes = self._recv_exact(4)
            if mask_bytes is None:
                return None
        payload = self._recv_exact(length)
        if payload is None:
            return None
        if masked:
            payload = bytearray(payload)
            for i in range(len(payload)):
                payload[i] ^= mask_bytes[i % 4]
            payload = bytes(payload)
        if opcode == 0x8:
            return None
        if opcode == 0x9:
            self._send_frame(payload, opcode=0xA)
            return self._recv_frame()
        if opcode == 0xA:
            return self._recv_frame()
        return payload.decode("utf-8") if opcode == 0x1 else payload


# ─── Training API Auth ────────────────────────────────────────────────────────

class TrainClient:
    """iFlytek Voice Clone training HTTP client (MD5-based auth)."""

    def __init__(self, app_id: str, api_key: str):
        self.app_id = app_id
        self.api_key = api_key
        self.token = None

    def _get_token(self) -> str:
        """Get auth token from iFlytek auth service."""
        ts = int(time.time() * 1000)
        body = {
            "base": {
                "appid": self.app_id,
                "version": "v1",
                "timestamp": str(ts),
            },
            "model": "remote",
        }
        body_json = json.dumps(body)
        key_sign = hashlib.md5((self.api_key + str(ts)).encode("utf-8")).hexdigest()
        sign = hashlib.md5((key_sign + body_json).encode("utf-8")).hexdigest()

        req = urllib.request.Request(
            AUTH_TOKEN_URL,
            data=body_json.encode("utf-8"),
            headers={
                "Authorization": sign,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        if result.get("retcode") != "000000":
            raise RuntimeError(f"Token auth failed: {result}")
        self.token = result["accesstoken"]
        return self.token

    def _ensure_token(self):
        if not self.token:
            self._get_token()

    def _sign_body(self, body) -> str:
        """Sign request body with MD5."""
        ts = int(time.time() * 1000)
        self._ts = ts
        body_str = str(body) if not isinstance(body, str) else body
        key_sign = hashlib.md5(body_str.encode("utf-8")).hexdigest()
        sign = hashlib.md5((self.api_key + str(ts) + key_sign).encode("utf-8")).hexdigest()
        return sign

    def _headers(self, sign: str) -> dict:
        return {
            "X-Sign": sign,
            "X-Token": self.token,
            "X-AppId": self.app_id,
            "X-Time": str(self._ts),
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict) -> dict:
        """POST JSON to training API."""
        self._ensure_token()
        sign = self._sign_body(body)
        headers = self._headers(sign)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            TRAIN_BASE_URL + path,
            data=data,
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_training_text(self, text_id: int = 5001) -> dict:
        """Get the list of training text segments."""
        return self._post("/task/traintext", {"textId": text_id})

    def create_task(
        self,
        name: str = "voice_clone_task",
        sex: int = 2,
        engine: str = "omni_v1",
        language: str = "cn",
        resource_name: str = None,
        callback_url: str = None,
    ) -> dict:
        """Create a training task. Returns full response (task_id in data)."""
        body = {
            "engineVersion": engine,
            "taskName": name,
            "sex": sex,
            "resourceType": 12,
            "resourceName": resource_name or name,
            "language": language,
        }
        if callback_url:
            body["callbackUrl"] = callback_url
        return self._post("/task/add", body)

    def upload_audio_url(
        self, task_id: int, audio_url: str, text_id: int = 5001, seg_id: int = 1
    ) -> dict:
        """Upload audio via URL to a training task."""
        body = {
            "taskId": task_id,
            "audioUrl": audio_url,
            "textId": text_id,
            "textSegId": seg_id,
        }
        return self._post("/audio/v1/add", body)

    def upload_audio_file(
        self, task_id: int, audio_path: str, text_id: int = 5001, seg_id: int = 1
    ) -> dict:
        """Upload local audio file to a training task using multipart form."""
        self._ensure_token()

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Build multipart body manually (no requests/requests_toolbelt)
        boundary = f"----PythonBoundary{int(time.time() * 1000)}"
        filename = os.path.basename(audio_path)

        # Determine MIME type
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".pcm": "audio/pcm"}
        mime_type = mime_map.get(ext, "application/octet-stream")

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        parts = []
        # File field
        parts.append(f"--{boundary}\r\n")
        parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n')
        parts.append(f"Content-Type: {mime_type}\r\n\r\n")
        parts.append(audio_data)
        parts.append(b"\r\n")
        # taskId field
        parts.append(f"--{boundary}\r\n")
        parts.append(f'Content-Disposition: form-data; name="taskId"\r\n\r\n')
        parts.append(f"{task_id}\r\n")
        # textId field
        parts.append(f"--{boundary}\r\n")
        parts.append(f'Content-Disposition: form-data; name="textId"\r\n\r\n')
        parts.append(f"{text_id}\r\n")
        # textSegId field
        parts.append(f"--{boundary}\r\n")
        parts.append(f'Content-Disposition: form-data; name="textSegId"\r\n\r\n')
        parts.append(f"{seg_id}\r\n")
        parts.append(f"--{boundary}--\r\n")

        # Combine into bytes
        body_bytes = b""
        for part in parts:
            if isinstance(part, str):
                body_bytes += part.encode("utf-8")
            else:
                body_bytes += part

        # Sign using the multipart body representation
        # The demo signs based on the formData object; we sign the raw body hash
        ts = int(time.time() * 1000)
        self._ts = ts
        # Use a simplified sign approach consistent with the API
        body_for_sign = str({"taskId": task_id, "textId": text_id, "textSegId": seg_id})
        key_sign = hashlib.md5(body_for_sign.encode("utf-8")).hexdigest()
        sign = hashlib.md5((self.api_key + str(ts) + key_sign).encode("utf-8")).hexdigest()

        headers = {
            "X-Sign": sign,
            "X-Token": self.token,
            "X-AppId": self.app_id,
            "X-Time": str(ts),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        req = urllib.request.Request(
            TRAIN_BASE_URL + "/task/submitWithAudio",
            data=body_bytes,
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def submit_task(self, task_id: int) -> dict:
        """Submit a training task for processing."""
        return self._post("/task/submit", {"taskId": task_id})

    def get_task_status(self, task_id: int) -> dict:
        """Query training task status."""
        return self._post("/task/result", {"taskId": task_id})


# ─── TTS WebSocket Auth ──────────────────────────────────────────────────────

def build_ws_auth_url(request_url: str, api_key: str, api_secret: str) -> str:
    """Build HMAC-SHA256 signed WebSocket authentication URL."""
    parsed = urllib.parse.urlparse(request_url)
    host = parsed.hostname
    path = parsed.path
    date = format_date_time(mktime(datetime.now().timetuple()))

    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature_sha).decode("utf-8")

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature_b64}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    params = {"host": host, "date": date, "authorization": authorization}
    return request_url + "?" + urllib.parse.urlencode(params)


# ─── TTS Synthesizer ─────────────────────────────────────────────────────────

class VoiceCloneSynthesizer:
    """Synthesize speech using a cloned voice via WebSocket."""

    def __init__(self, app_id, api_key, api_secret, res_id, args):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.res_id = res_id
        self.args = args
        self.audio_chunks = []
        self.error = None
        self.sid = None
        self.done = threading.Event()

    def _build_request(self, text: str) -> dict:
        a = self.args
        encoding_map = {"mp3": "lame", "pcm": "raw", "speex": "speex", "opus": "opus"}
        audio_encoding = encoding_map.get(a.format, a.format)

        return {
            "header": {
                "app_id": self.app_id,
                "res_id": self.res_id,
                "status": 2,
            },
            "parameter": {
                "tts": {
                    "vcn": DEFAULT_VCN,
                    "volume": a.volume,
                    "speed": a.speed,
                    "pitch": a.pitch,
                    "bgs": 0,
                    "reg": 0,
                    "rdn": 0,
                    "rhy": 0,
                    "pybuffer": 1,
                    "audio": {
                        "encoding": audio_encoding,
                        "sample_rate": a.sample_rate,
                        "channels": 1,
                        "bit_depth": 16,
                        "frame_size": 0,
                    },
                    "pybuf": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                    },
                },
            },
            "payload": {
                "text": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain",
                    "status": 2,
                    "seq": 0,
                    "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
                },
            },
        }

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
            code = msg.get("header", {}).get("code", -1)
            self.sid = msg.get("header", {}).get("sid", self.sid)

            if code != 0:
                err_msg = msg.get("header", {}).get("message", "unknown error")
                self.error = f"Error (code {code}): {err_msg}"
                ws.close()
                return

            if "payload" in msg and "audio" in msg["payload"]:
                audio_data = msg["payload"]["audio"].get("audio", "")
                if audio_data:
                    self.audio_chunks.append(base64.b64decode(audio_data))
                status = msg["payload"]["audio"].get("status", 0)
                if status == 2:
                    ws.close()
        except Exception as e:
            self.error = f"Parse error: {e}"
            ws.close()

    def _on_error(self, ws, error):
        self.error = str(error)
        self.done.set()

    def _on_close(self, ws):
        self.done.set()

    def _on_open(self, ws):
        def send_text():
            try:
                request = self._build_request(self.text)
                ws.send(json.dumps(request))
            except Exception as e:
                self.error = f"Send error: {e}"
                ws.close()

        t = threading.Thread(target=send_text, daemon=True)
        t.start()

    def synthesize(self, text: str) -> bytes:
        self.text = text
        self.audio_chunks = []
        self.error = None
        self.done.clear()

        auth_url = build_ws_auth_url(TTS_WS_URL, self.api_key, self.api_secret)

        ws = SimpleWebSocket(
            auth_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )

        ws_thread = threading.Thread(target=ws.connect, daemon=True)
        ws_thread.start()

        self.done.wait(timeout=120)

        if self.error:
            raise RuntimeError(self.error)

        return b"".join(self.audio_chunks)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def cmd_train(args):
    """Handle all training subcommands."""
    app_id = os.environ.get("IFLY_APP_ID")
    api_key = os.environ.get("IFLY_API_KEY")

    if not app_id or not api_key:
        missing = []
        if not app_id:
            missing.append("IFLY_APP_ID")
        if not api_key:
            missing.append("IFLY_API_KEY")
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    client = TrainClient(app_id, api_key)

    if args.train_cmd == "get-text":
        text_id = getattr(args, "text_id", 5001)
        result = client.get_training_text(text_id)
        if "data" in result and "textSegs" in result["data"]:
            segs = result["data"]["textSegs"]
            print(f"Training text set (textId={text_id}), {len(segs)} segments:\n")
            for seg in segs:
                print(f"  segId: {seg['segId']}")
                print(f"  text:  {seg['segText']}")
                print()
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.train_cmd == "create":
        sex_map = {"male": 1, "female": 2, "m": 1, "f": 2, "1": 1, "2": 2}
        sex = sex_map.get(str(args.sex).lower(), 2)
        result = client.create_task(
            name=args.name,
            sex=sex,
            engine=args.engine,
            language=args.language,
            resource_name=args.resource_name,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if "data" in result:
            print(f"\n✅ Task created. task_id: {result['data']}", file=sys.stderr)

    elif args.train_cmd == "upload":
        if args.audio_url:
            result = client.upload_audio_url(
                args.task_id, args.audio_url, args.text_id, args.seg_id
            )
        elif args.audio:
            result = client.upload_audio_file(
                args.task_id, args.audio, args.text_id, args.seg_id
            )
        else:
            print("Error: Provide --audio (local file) or --audio-url", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.train_cmd == "submit":
        result = client.submit_task(args.task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.train_cmd == "status":
        result = client.get_task_status(args.task_id)
        if "data" in result:
            data = result["data"]
            status = data.get("trainStatus")
            status_text = {-1: "⏳ Training in progress...", 1: "✅ Training succeeded!", 0: "❌ Training failed"}
            print(status_text.get(status, f"Unknown status: {status}"), file=sys.stderr)
            if status == 1 and "assetId" in data:
                print(f"\n🎉 Voice resource ID (res_id): {data['assetId']}", file=sys.stderr)
                print(f"Use this for synthesis: --res-id {data['assetId']}", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.train_cmd == "quick":
        # Quick: create → upload → submit → (optionally) wait
        sex_map = {"male": 1, "female": 2, "m": 1, "f": 2, "1": 1, "2": 2}
        sex = sex_map.get(str(args.sex).lower(), 2)

        print("Creating training task...", file=sys.stderr)
        create_result = client.create_task(
            name=args.name, sex=sex, engine=args.engine, language=args.language
        )
        if "data" not in create_result:
            print(f"Failed to create task: {json.dumps(create_result, ensure_ascii=False)}", file=sys.stderr)
            sys.exit(1)
        task_id = create_result["data"]
        print(f"Task created: {task_id}", file=sys.stderr)

        print(f"Uploading audio: {args.audio}", file=sys.stderr)
        if args.audio.startswith("http://") or args.audio.startswith("https://"):
            upload_result = client.upload_audio_url(task_id, args.audio, args.text_id, args.seg_id)
        else:
            upload_result = client.upload_audio_file(task_id, args.audio, args.text_id, args.seg_id)
        print(f"Upload result: {json.dumps(upload_result, ensure_ascii=False)}", file=sys.stderr)

        print("Submitting task...", file=sys.stderr)
        submit_result = client.submit_task(task_id)
        print(f"Submit result: {json.dumps(submit_result, ensure_ascii=False)}", file=sys.stderr)

        if args.wait:
            print("Waiting for training to complete (polling every 30s)...", file=sys.stderr)
            while True:
                time.sleep(30)
                status_result = client.get_task_status(task_id)
                if "data" in status_result:
                    st = status_result["data"].get("trainStatus")
                    if st == 1:
                        res_id = status_result["data"].get("assetId", "")
                        print(f"\n✅ Training complete! res_id: {res_id}", file=sys.stderr)
                        print(res_id)
                        return
                    elif st == 0:
                        print("\n❌ Training failed.", file=sys.stderr)
                        print(json.dumps(status_result, ensure_ascii=False, indent=2))
                        sys.exit(1)
                    else:
                        print("  Still training...", file=sys.stderr)
        else:
            print(f"\n📋 Task submitted. task_id: {task_id}", file=sys.stderr)
            print(f"Check status: python voiceclone.py train status --task-id {task_id}", file=sys.stderr)
            print(task_id)

    else:
        print(f"Unknown train command: {args.train_cmd}", file=sys.stderr)
        sys.exit(1)


def cmd_synth(args):
    """Handle synthesis subcommand."""
    app_id = os.environ.get("IFLY_APP_ID")
    api_key = os.environ.get("IFLY_API_KEY")
    api_secret = os.environ.get("IFLY_API_SECRET")

    missing = []
    if not app_id:
        missing.append("IFLY_APP_ID")
    if not api_key:
        missing.append("IFLY_API_KEY")
    if not api_secret:
        missing.append("IFLY_API_SECRET")
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    if not args.res_id:
        print("Error: --res-id is required for synthesis (the voice model ID from training)", file=sys.stderr)
        sys.exit(1)

    # Determine input text
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read().strip()
    elif args.text:
        text = args.text
    else:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        else:
            print("Error: No input. Pass text as argument, use --file, or pipe via stdin.", file=sys.stderr)
            sys.exit(1)

    if not text:
        print("Error: Input text is empty.", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    ext_map = {"mp3": ".mp3", "pcm": ".pcm", "speex": ".speex", "opus": ".opus"}
    if args.output:
        output_path = args.output
    else:
        output_path = "output" + ext_map.get(args.format, ".mp3")

    print(f"Synthesizing with cloned voice (res_id={args.res_id})...", file=sys.stderr)
    synth = VoiceCloneSynthesizer(app_id, api_key, api_secret, args.res_id, args)

    try:
        audio_data = synth.synthesize(text)
    except RuntimeError as e:
        print(f"Synthesis failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not audio_data:
        print("Error: No audio data received.", file=sys.stderr)
        sys.exit(1)

    with open(output_path, "wb") as f:
        f.write(audio_data)

    size_kb = len(audio_data) / 1024
    print(f"✅ Audio saved to {output_path} ({size_kb:.1f} KB)", file=sys.stderr)
    if synth.sid:
        print(f"SID: {synth.sid}", file=sys.stderr)

    print(os.path.abspath(output_path))


def main():
    parser = argparse.ArgumentParser(
        description="iFlytek Voice Clone (声音复刻) — train a custom voice and synthesize speech.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Training workflow
  %(prog)s train get-text                                    # Get training text list
  %(prog)s train create --name "MyVoice" --sex female        # Create task
  %(prog)s train upload --task-id ID --audio voice.wav       # Upload audio
  %(prog)s train submit --task-id ID                         # Submit for training
  %(prog)s train status --task-id ID                         # Check status → res_id

  # Quick one-shot training
  %(prog)s train quick --audio voice.wav --name "MyVoice" --sex female --wait

  # Synthesis with cloned voice
  %(prog)s synth "你好世界" --res-id YOUR_RES_ID --output hello.mp3
  %(prog)s synth --file article.txt --res-id YOUR_RES_ID -o article.mp3
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # ── train subcommand ──
    train_parser = subparsers.add_parser("train", help="Voice training operations")
    train_sub = train_parser.add_subparsers(dest="train_cmd", help="Training operation")

    # train get-text
    gt = train_sub.add_parser("get-text", help="Get training text list")
    gt.add_argument("--text-id", type=int, default=5001, help="Text set ID (default: 5001)")

    # train create
    cr = train_sub.add_parser("create", help="Create a training task")
    cr.add_argument("--name", required=True, help="Task name")
    cr.add_argument("--sex", required=True, help="Voice gender: male/female (or 1/2)")
    cr.add_argument("--engine", default="omni_v1", help="Engine version (default: omni_v1 for multi-style)")
    cr.add_argument("--language", default="cn", choices=["cn", "en", "jp", "ko", "ru"], help="Language (default: cn)")
    cr.add_argument("--resource-name", help="Resource name (default: same as task name)")

    # train upload
    up = train_sub.add_parser("upload", help="Upload audio to a training task")
    up.add_argument("--task-id", type=int, required=True, help="Task ID")
    up.add_argument("--audio", help="Local audio file path (wav/mp3/m4a/pcm)")
    up.add_argument("--audio-url", help="Audio URL (http/https)")
    up.add_argument("--text-id", type=int, default=5001, help="Text set ID (default: 5001)")
    up.add_argument("--seg-id", type=int, default=1, help="Text segment ID (default: 1)")

    # train submit
    su = train_sub.add_parser("submit", help="Submit training task")
    su.add_argument("--task-id", type=int, required=True, help="Task ID")

    # train status
    st = train_sub.add_parser("status", help="Query training task status")
    st.add_argument("--task-id", type=int, required=True, help="Task ID")

    # train quick
    qu = train_sub.add_parser("quick", help="Quick: create + upload + submit in one step")
    qu.add_argument("--audio", required=True, help="Audio file path or URL")
    qu.add_argument("--name", default="voice_clone_task", help="Task name")
    qu.add_argument("--sex", default="female", help="Voice gender: male/female")
    qu.add_argument("--engine", default="omni_v1", help="Engine version (default: omni_v1)")
    qu.add_argument("--language", default="cn", choices=["cn", "en", "jp", "ko", "ru"], help="Language")
    qu.add_argument("--text-id", type=int, default=5001, help="Text set ID (default: 5001)")
    qu.add_argument("--seg-id", type=int, default=1, help="Text segment ID (default: 1)")
    qu.add_argument("--wait", action="store_true", help="Wait for training to complete (polls every 30s)")

    # ── synth subcommand ──
    synth_parser = subparsers.add_parser("synth", help="Synthesize speech with cloned voice")
    synth_parser.add_argument("text", nargs="?", default=None, help="Text to synthesize")
    synth_parser.add_argument("--file", "-f", help="Read text from a file")
    synth_parser.add_argument("--output", "-o", help="Output audio file path (default: output.mp3)")
    synth_parser.add_argument("--res-id", required=True, help="Voice resource ID from training")
    synth_parser.add_argument("--format", choices=["mp3", "pcm", "speex", "opus"], default="mp3", help="Audio format (default: mp3)")
    synth_parser.add_argument("--sample-rate", type=int, default=16000, choices=[8000, 16000, 24000], help="Sample rate (default: 16000)")
    synth_parser.add_argument("--speed", type=int, default=50, help="Speed 0-100 (default: 50)")
    synth_parser.add_argument("--volume", type=int, default=50, help="Volume 0-100 (default: 50)")
    synth_parser.add_argument("--pitch", type=int, default=50, help="Pitch 0-100 (default: 50)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "train":
        if not args.train_cmd:
            train_parser.print_help()
            sys.exit(1)
        cmd_train(args)
    elif args.command == "synth":
        cmd_synth(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
