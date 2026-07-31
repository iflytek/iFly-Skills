# MiniMax TTS (text-to-audio)

Synthesize speech from text using the MiniMax Text-to-Audio `t2a_v2` HTTP endpoint. Supports the global endpoint (`api.minimax.io`) and the China endpoint (`api.minimaxi.com`), configurable voice and prosody, and mp3/wav/flac/pcm output. Pure Python standard library — no pip dependencies.

## Quick start

### 1. Configure environment variables

```bash
export MINIMAX_GROUP_ID="your_group_id"
export MINIMAX_API_KEY="your_api_key"
```

### 2. Synthesize

```bash
# Global endpoint, default model and voice, mp3 output
python3 scripts/minimax_tts.py --text "Hello, this is MiniMax text to audio." --output hello.mp3

# China endpoint
python3 scripts/minimax_tts.py --text "你好，欢迎使用语音合成。" --region cn --output cn.mp3

# Configure voice and prosody
python3 scripts/minimax_tts.py --text "Slower and louder." \
    --voice male-qn-qingse --speed 0.8 --vol 8 --pitch 3 --output tuned.mp3
```

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--text` / `--text-file` | - | Text to synthesize (one required) |
| `--output` | `output.mp3` | Output audio file path |
| `--region` | `global` | `global` or `cn` endpoint |
| `--model` | `speech-2.8-hd` | Speech model id |
| `--voice` | `male-qn-qingse` | Speaker voice id |
| `--speed` | `1.0` | Speed 0.5–2.0 (1.0 = normal) |
| `--vol` | `10` | Volume 0–10 (10 = normal) |
| `--pitch` | `0` | Pitch −12 to 12 (0 = normal) |
| `--audio-format` | `mp3` | mp3, wav, flac, pcm |
| `--sample-rate` | `32000` | Sample rate in Hz |
| `--bitrate` | `128000` | Bit rate |
| `--language-boost` | - | Language boost tag (zh, en, auto) |
| `--stream` | `false` | Request server-side streaming |

## Inspect available voices and models

```bash
python3 scripts/minimax_tts.py --action list_voices
python3 scripts/minimax_tts.py --action list_models
```

## API reference

- Global: https://platform.minimax.io/docs/api-reference/speech-t2a-http
- China: https://platform.minimaxi.com/docs/api-reference/speech-t2a-http
