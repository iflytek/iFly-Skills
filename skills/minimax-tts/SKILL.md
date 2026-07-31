---
name: minimax-tts
description: Use when user asks to synthesize speech, convert text to audio, or read text aloud using the MiniMax speech platform. MiniMax Text-to-Audio (t2a_v2) — generate spoken audio from text with configurable voice, speed, volume, pitch, audio format, and sample rate over HTTP. Supports both global and China endpoints. Pure Python stdlib, no pip dependencies.
metadata: {
  "homepage": "https://platform.minimax.io/docs/api-reference/speech-t2a-http",
  "openclaw": "{\"emoji\":\"🎙️\",\"dimensions\":[\"MiniMax TTS\",\"text to audio\"],\"user_instructions\":[\"read this text aloud\",\"convert text to speech\",\"generate audio from text\"],\"requires\":{\"bins\":[\"python3\"],\"env\":[\"MINIMAX_GROUP_ID\",\"MINIMAX_API_KEY\"]},\"primaryEnv\":\"MINIMAX_API_KEY\"}"
}
---

# MiniMax TTS (text-to-audio)

Convert text to speech with MiniMax's Text-to-Audio `t2a_v2` HTTP endpoint. Choose between the **global** endpoint (`api.minimax.io`) and the **China** endpoint (`api.minimaxi.com`) via `--region`.

API docs:
- Global: https://platform.minimax.io/docs/api-reference/speech-t2a-http
- China: https://platform.minimaxi.com/docs/api-reference/speech-t2a-http

## Core features

- **Text to audio**: single HTTP POST to `https://api.minimax.io/v1/t2a_v2` (global) or `https://api.minimaxi.com/v1/t2a_v2` (China)
- **Bearer auth**: send `Authorization: Bearer $MINIMAX_API_KEY`; the group id is passed as the `GroupId` query parameter
- **Configurable voice**: `--voice` selects the speaker; `--speed`, `--vol`, `--pitch` adjust prosody
- **Audio settings**: `--audio-format` (mp3, wav, flac, pcm), `--sample-rate`, and `--bitrate`
- **Language boost**: `--language-boost` improves pronunciation for the target language
- **Multi-format output**: decoded audio is written to the `--output` path

---

## Setup

1. Create an application at the MiniMax platform and obtain:
   - **Group ID**: the group that owns the API key
   - **API Key**: the bearer token used for authorization
2. Set environment variables:

```bash
export MINIMAX_GROUP_ID="your_group_id"
export MINIMAX_API_KEY="your_api_key"
```

Global users use `api.minimax.io`; users in China use `api.minimaxi.com` (pass `--region cn`).

---

## Usage

### Scenario 1: synthesize with defaults

```bash
# Global endpoint, default model (speech-2.8-hd), mp3 output
python3 scripts/minimax_tts.py --text "Hello, this is MiniMax text to audio."

# Write to a specific file
python3 scripts/minimax_tts.py --text "Welcome aboard." --output welcome.mp3
```

### Scenario 2: configure voice and prosody

```bash
# Pick a speaker and adjust speed/volume/pitch
python3 scripts/minimax_tts.py --text "Slower and louder." \
    --voice male-qn-qingse --speed 0.8 --vol 8 --pitch 3 --output tuned.mp3
```

### Scenario 3: use the China endpoint

```bash
# Route to the China region endpoint
python3 scripts/minimax_tts.py --text "你好，欢迎使用语音合成。" --region cn --output cn.mp3
```

### Scenario 4: list available voices and models

```bash
python3 scripts/minimax_tts.py --action list_voices
python3 scripts/minimax_tts.py --action list_models
```

---

## Input parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--action` | `synthesize` (default) \| `list_voices` \| `list_models` | synthesize |
| `--text` | Text to synthesize (mutually exclusive with `--text-file`) | - |
| `--text-file` | Path to a text file (mutually exclusive with `--text`) | - |
| `--output` | Output audio file path | output.mp3 |
| `--region` | `global` or `cn` endpoint | global |
| `--model` | Speech model id | speech-2.8-hd |
| `--voice` | Speaker voice id | male-qn-qingse |
| `--speed` | Speed (0.5–2.0, 1.0 = normal) | 1.0 |
| `--vol` | Volume (0–10, 10 = normal) | 10 |
| `--pitch` | Pitch (−12 to 12, 0 = normal) | 0 |
| `--audio-format` | mp3, wav, flac, pcm | mp3 |
| `--sample-rate` | 8000, 16000, 24000, 32000, 44100 | 32000 |
| `--bitrate` | Bit rate (128000, 256000, …) | 128000 |
| `--language-boost` | Language boost tag (e.g. `zh`, `en`, `auto`) | - |
| `--stream` | Request server-side streaming | false |

### Response

```json
{
  "success": true,
  "output_path": "/absolute/path/to/output.mp3",
  "region": "global",
  "model": "speech-2.8-hd",
  "voice": "male-qn-qingse",
  "audio_format": "mp3",
  "text_length": 32,
  "total_size_bytes": 47832,
  "total_size_kb": 46.71,
  "status_code": 0
}
```

---

## Workflow

1. **Read input**: parse `--text` or `--text-file`
2. **Resolve endpoint**: select `global` or `cn` URL
3. **Build request body**: `model`, `text`, `voice_setting`, `audio_setting`, `language_boost`, `output_format`
4. **Authorize**: `Authorization: Bearer $MINIMAX_API_KEY`, `GroupId=$MINIMAX_GROUP_ID` query
5. **Send**: POST JSON to `/v1/t2a_v2?GroupId=...`
6. **Decode**: base64-decode `data.audio` into the output file
7. **Return**: JSON with the absolute output path and metadata

---

## Error handling

The MiniMax API returns errors in `base_resp.status_code`. Common codes:

| Code | Meaning | Suggestion |
|------|---------|------------|
| `1004` | Unauthorized | Check `MINIMAX_API_KEY` and that the key belongs to the group |
| `1008` | Group has no authority | Confirm the group has permission to the requested model |
| `1027` | Group not found | Check `MINIMAX_GROUP_ID` |
| `1000` | Invalid request | Verify the request body and required fields |
| `1005` | Text too long | Split the text into shorter segments |

---

## Configuration

### Dependencies

No pip dependencies. Uses the Python standard library only (`urllib`, `json`, `base64`).

### Environment variables

```bash
export MINIMAX_GROUP_ID="your_group_id"
export MINIMAX_API_KEY="your_api_key"
```
