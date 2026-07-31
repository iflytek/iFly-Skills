#!/usr/bin/env python3
"""
MiniMax Text-to-Audio (t2a_v2).

Synthesize speech from text over the MiniMax HTTP endpoint.

Endpoints:
  global: https://api.minimax.io/v1/t2a_v2
  cn:     https://api.minimaxi.com/v1/t2a_v2

Authentication: HTTP header `Authorization: Bearer <api_key>` plus the
`GroupId=<group_id>` query parameter.

Environment variables (required for synthesis):
  MINIMAX_GROUP_ID - the group that owns the API key
  MINIMAX_API_KEY  - the bearer token used for authorization

Examples:
  python3 scripts/minimax_tts.py --text "Hello world" --output hello.mp3
  python3 scripts/minimax_tts.py --text "你好" --region cn --output cn.mp3
  python3 scripts/minimax_tts.py --action list_voices
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


# --- Constants -----------------------------------------------------------------

# Regional endpoints for the t2a_v2 text-to-audio operation.
ENDPOINTS = {
    "global": "https://api.minimax.io/v1/t2a_v2",
    "cn": "https://api.minimaxi.com/v1/t2a_v2",
}

# Speech models supported by the t2a_v2 endpoint.
SPEECH_MODELS = [
    "speech-2.8-hd",
    "speech-2.8-turbo",
    "speech-2.6-hd",
    "speech-2.6-turbo",
    "speech-02-hd",
    "speech-02-turbo",
    "speech-01-hd",
    "speech-01-turbo",
]

DEFAULT_MODEL = "speech-2.8-hd"

# Audio formats accepted by the audio_setting.format field.
AUDIO_FORMATS = ["mp3", "wav", "flac", "pcm"]

# Curated voice presets (the platform exposes many more).
VOICE_LIST = [
    {"name": "Qingse (male)", "voice": "male-qn-qingse", "lang": "Chinese"},
    {"name": "Huoli (male)", "voice": "male-qn-jingying", "lang": "Chinese"},
    {"name": "Bingcheng (male)", "voice": "male-qn-badao", "lang": "Chinese"},
    {"name": "Bokan (male)", "voice": "male-qn-daxuesheng", "lang": "Chinese"},
    {"name": "Yuanqi (female)", "voice": "female-shaonv", "lang": "Chinese"},
    {"name": "Wenwan (female)", "voice": "female-yujie", "lang": "Chinese"},
    {"name": "Chunzhen (female)", "voice": "female-chengshu", "lang": "Chinese"},
    {"name": "Zhiyin (female)", "voice": "female-tianmei", "lang": "Chinese"},
    {"name": "Yongai (male)", "voice": "presenter_male", "lang": "Chinese"},
    {"name": "Yongxiang (female)", "voice": "presenter_female", "lang": "Chinese"},
    {"name": "Gentleman (male, English)", "voice": "English_in_Lei", "lang": "English"},
    {"name": "Radiant (female, English)", "voice": "English_in_Sophia", "lang": "English"},
    {"name": "Deep (male, English)", "voice": "English_in_Caleb", "lang": "English"},
]

DEFAULT_VOICE = "male-qn-qingse"

TEXT_MAX_BYTES = 1_000_000  # 1 MB safety bound for the text payload.


# --- Credentials ---------------------------------------------------------------

def get_env_credentials():
    """Load and validate group id / api key from environment variables."""
    group_id = os.getenv("MINIMAX_GROUP_ID")
    api_key = os.getenv("MINIMAX_API_KEY")

    missing = [
        name for name, val in [
            ("MINIMAX_GROUP_ID", group_id),
            ("MINIMAX_API_KEY", api_key),
        ] if not val
    ]

    if missing:
        error_response = {
            "success": False,
            "error": {
                "code": "MISSING_ENV_VARS",
                "message": f"Missing required environment variables: {', '.join(missing)}",
                "cause": "MiniMax credentials are not configured",
                "suggestion": "Set MINIMAX_GROUP_ID and MINIMAX_API_KEY in the environment",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    return group_id, api_key


# --- TTS client ----------------------------------------------------------------

class MiniMaxTTSClient:
    """MiniMax t2a_v2 HTTP client (stdlib only)."""

    def __init__(self, group_id, api_key, region="global"):
        if region not in ENDPOINTS:
            raise ValueError(f"Unknown region: {region}. Use 'global' or 'cn'.")
        self.group_id = group_id
        self.api_key = api_key
        self.region = region
        self.endpoint = ENDPOINTS[region]

    def _build_url(self):
        """Append the GroupId query parameter to the endpoint."""
        sep = "&" if "?" in self.endpoint else "?"
        return f"{self.endpoint}{sep}GroupId={urllib.parse.quote(self.group_id, safe='')}"

    def _build_body(self, text, model, voice, speed, vol, pitch,
                    audio_format, sample_rate, bitrate, language_boost, stream):
        """Build the t2a_v2 request body."""
        body = {
            "model": model,
            "text": text,
            "voice_setting": {
                "voice_id": voice,
                "speed": speed,
                "vol": vol,
                "pitch": pitch,
            },
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "format": audio_format,
                "channel": 1,
            },
            "output_format": "hex",
        }
        if language_boost:
            body["language_boost"] = language_boost
        if stream:
            body["stream"] = True
        return body

    def synthesize(
        self,
        text,
        output_path,
        model=DEFAULT_MODEL,
        voice=DEFAULT_VOICE,
        speed=1.0,
        vol=10,
        pitch=0,
        audio_format="mp3",
        sample_rate=32000,
        bitrate=128000,
        language_boost=None,
        stream=False,
    ):
        """Synthesize speech and write the decoded audio to output_path."""
        text_bytes = text.encode("utf-8")
        if len(text_bytes) > TEXT_MAX_BYTES:
            error_response = {
                "success": False,
                "error": {
                    "code": "TEXT_TOO_LONG",
                    "message": f"Text too long: {len(text_bytes)} bytes (max {TEXT_MAX_BYTES})",
                    "cause": "Text exceeds the safety bound for a single request",
                    "suggestion": "Split the text into shorter segments and synthesize each separately",
                }
            }
            raise ValueError(json.dumps(error_response, ensure_ascii=False, indent=2))

        if audio_format not in AUDIO_FORMATS:
            raise ValueError(f"Unsupported audio format: {audio_format}")

        url = self._build_url()
        body = self._build_body(
            text, model, voice, speed, vol, pitch,
            audio_format, sample_rate, bitrate, language_boost, stream,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        print(f"[1/3] Requesting MiniMax t2a_v2 ({self.region})...", file=sys.stderr)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            payload = self._safe_json(exc.read())
            error_response = {
                "success": False,
                "error": {
                    "code": f"HTTP_{exc.code}",
                    "message": exc.reason,
                    "cause": "The MiniMax API rejected the request",
                    "suggestion": "Inspect base_resp in the response payload for details",
                    "response": payload,
                }
            }
            raise ConnectionError(json.dumps(error_response, ensure_ascii=False, indent=2)) from exc
        except urllib.error.URLError as exc:
            error_response = {
                "success": False,
                "error": {
                    "code": "CONNECTION_FAILED",
                    "message": f"Failed to connect: {exc.reason}",
                    "cause": "Network connection failed",
                    "suggestion": "Check network connectivity and the selected region endpoint",
                }
            }
            raise ConnectionError(json.dumps(error_response, ensure_ascii=False, indent=2)) from exc

        response = self._safe_json(raw)

        base_resp = response.get("base_resp", {})
        status_code = base_resp.get("status_code")
        if status_code not in (0, None):
            error_response = {
                "success": False,
                "error": {
                    "code": f"API_ERROR_{status_code}",
                    "message": base_resp.get("status_msg", "Unknown MiniMax error"),
                    "cause": "The MiniMax API reported a non-success status",
                    "suggestion": self._error_suggestion(status_code),
                }
            }
            raise RuntimeError(json.dumps(error_response, ensure_ascii=False, indent=2))

        data_block = response.get("data", {})
        audio_field = data_block.get("audio")
        if not audio_field:
            error_response = {
                "success": False,
                "error": {
                    "code": "NO_AUDIO_DATA",
                    "message": "No audio data received from the API",
                    "cause": "The response did not contain data.audio",
                    "suggestion": "Verify the text is non-empty and the model/voice are valid",
                }
            }
            raise RuntimeError(json.dumps(error_response, ensure_ascii=False, indent=2))

        try:
            audio_bytes = base64.b64decode(audio_field)
        except Exception as exc:
            error_response = {
                "success": False,
                "error": {
                    "code": "AUDIO_DECODE_FAILED",
                    "message": f"Failed to decode audio: {exc}",
                    "cause": "data.audio is not valid base64",
                    "suggestion": "Check output_format and try a non-streaming request",
                }
            }
            raise RuntimeError(json.dumps(error_response, ensure_ascii=False, indent=2)) from exc

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        print(f"[2/3] Decoded {len(audio_bytes)} bytes of audio.", file=sys.stderr)
        with open(output_path, "wb") as fh:
            fh.write(audio_bytes)

        print(f"[3/3] Saved audio to: {output_path}", file=sys.stderr)

        result = {
            "success": True,
            "output_path": os.path.abspath(output_path),
            "region": self.region,
            "model": model,
            "voice": voice,
            "audio_format": audio_format,
            "text_length": len(text),
            "total_size_bytes": len(audio_bytes),
            "total_size_kb": round(len(audio_bytes) / 1024, 2),
            "status_code": status_code,
        }
        return result

    @staticmethod
    def _safe_json(raw):
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"raw": raw.decode("utf-8", errors="replace")}

    @staticmethod
    def _error_suggestion(code):
        suggestions = {
            1004: "Check MINIMAX_API_KEY and that it belongs to the group",
            1008: "Confirm the group has permission for the requested model",
            1027: "Check MINIMAX_GROUP_ID",
            1000: "Verify the request body and required fields",
            1005: "Split the text into shorter segments",
        }
        return suggestions.get(code, "See the MiniMax API documentation for this status code")


# --- Helpers -------------------------------------------------------------------

def _resolve_output_path(output, audio_format):
    """Ensure the output path ends with a sensible extension."""
    ext_map = {"mp3": ".mp3", "wav": ".wav", "flac": ".flac", "pcm": ".pcm"}
    ext = ext_map.get(audio_format, "")
    if ext and not os.path.splitext(output)[1]:
        return output + ext
    return output


def _read_text_file(path):
    """Read text content from a file with validation."""
    if not os.path.exists(path):
        error_response = {
            "success": False,
            "error": {
                "code": "FILE_NOT_FOUND",
                "message": f"Text file not found: {path}",
                "cause": "The specified text file does not exist",
                "suggestion": "Check the file path",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read().strip()

    if not content:
        error_response = {
            "success": False,
            "error": {
                "code": "EMPTY_FILE",
                "message": "Text file is empty",
                "cause": "The text file contains no content",
                "suggestion": "Add the text to synthesize into the file",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    return content


# --- CLI -----------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="minimax_tts.py",
        description="MiniMax Text-to-Audio (t2a_v2) - synthesize speech from text",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default synthesis (global endpoint, mp3)
  python3 scripts/minimax_tts.py --text "Hello world" --output hello.mp3

  # China endpoint
  python3 scripts/minimax_tts.py --text "你好" --region cn --output cn.mp3

  # Adjust voice and prosody
  python3 scripts/minimax_tts.py --text "Slower." --voice male-qn-qingse --speed 0.8 --vol 8

  # List available voices / models
  python3 scripts/minimax_tts.py --action list_voices
  python3 scripts/minimax_tts.py --action list_models
        """,
    )

    parser.add_argument(
        "--action", "-a",
        choices=["synthesize", "list_voices", "list_models"],
        default="synthesize",
        help="Action: synthesize | list_voices | list_models (default: synthesize)",
    )

    text_group = parser.add_mutually_exclusive_group()
    text_group.add_argument("--text", "-t", help="Text to synthesize")
    text_group.add_argument("--text-file", "-f", help="Path to a text file to synthesize")

    parser.add_argument("--output", "-o", default="output.mp3", help="Output audio file path (default: output.mp3)")

    parser.add_argument("--region", choices=["global", "cn"], default="global", help="Endpoint region (default: global)")

    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Speech model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Speaker voice id (default: {DEFAULT_VOICE})")

    parser.add_argument("--speed", type=float, default=1.0, help="Speed 0.5-2.0, 1.0=normal (default: 1.0)")
    parser.add_argument("--vol", type=int, default=10, help="Volume 0-10, 10=normal (default: 10)")
    parser.add_argument("--pitch", type=int, default=0, help="Pitch -12 to 12, 0=normal (default: 0)")

    parser.add_argument(
        "--audio-format",
        choices=AUDIO_FORMATS,
        default="mp3",
        help="Audio format (default: mp3)",
    )
    parser.add_argument("--sample-rate", type=int, default=32000, help="Sample rate in Hz (default: 32000)")
    parser.add_argument("--bitrate", type=int, default=128000, help="Bit rate (default: 128000)")
    parser.add_argument("--language-boost", help="Language boost tag, e.g. zh, en, auto")
    parser.add_argument("--stream", action="store_true", help="Request server-side streaming")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.action == "list_voices":
        print(json.dumps({"voices": VOICE_LIST}, ensure_ascii=False, indent=2))
        return

    if args.action == "list_models":
        print(json.dumps({"models": SPEECH_MODELS, "default": DEFAULT_MODEL}, ensure_ascii=False, indent=2))
        return

    group_id, api_key = get_env_credentials()

    if not args.text and not args.text_file:
        error_response = {
            "success": False,
            "error": {
                "code": "MISSING_INPUT",
                "message": "--text or --text-file is required",
                "cause": "No text was provided for synthesis",
                "suggestion": "Pass --text with the content or --text-file with a path",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    text = _read_text_file(args.text_file) if args.text_file else args.text.strip()
    if not text:
        error_response = {
            "success": False,
            "error": {
                "code": "EMPTY_TEXT",
                "message": "Input text is empty",
                "cause": "The provided text contains no content",
                "suggestion": "Provide non-empty text to synthesize",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    if not 0.5 <= args.speed <= 2.0:
        error_response = {
            "success": False,
            "error": {
                "code": "INVALID_PARAMETER",
                "message": f"--speed must be between 0.5 and 2.0, got {args.speed}",
                "cause": "Speed out of range",
                "suggestion": "Set --speed between 0.5 and 2.0",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    if not 0 <= args.vol <= 10:
        error_response = {
            "success": False,
            "error": {
                "code": "INVALID_PARAMETER",
                "message": f"--vol must be between 0 and 10, got {args.vol}",
                "cause": "Volume out of range",
                "suggestion": "Set --vol between 0 and 10",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    if not -12 <= args.pitch <= 12:
        error_response = {
            "success": False,
            "error": {
                "code": "INVALID_PARAMETER",
                "message": f"--pitch must be between -12 and 12, got {args.pitch}",
                "cause": "Pitch out of range",
                "suggestion": "Set --pitch between -12 and 12",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    output_path = _resolve_output_path(args.output, args.audio_format)
    client = MiniMaxTTSClient(group_id, api_key, region=args.region)

    try:
        result = client.synthesize(
            text=text,
            output_path=output_path,
            model=args.model,
            voice=args.voice,
            speed=args.speed,
            vol=args.vol,
            pitch=args.pitch,
            audio_format=args.audio_format,
            sample_rate=args.sample_rate,
            bitrate=args.bitrate,
            language_boost=args.language_boost,
            stream=args.stream,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(1)
    except (ConnectionError, RuntimeError, ValueError) as exc:
        try:
            print(json.dumps(json.loads(str(exc)), ensure_ascii=False, indent=2), file=sys.stderr)
        except (json.JSONDecodeError, ValueError):
            print(str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        error_response = {
            "success": False,
            "error": {
                "code": "UNEXPECTED_ERROR",
                "message": str(exc),
                "cause": "An unexpected error occurred",
                "suggestion": "Review the error message or contact support",
            }
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
