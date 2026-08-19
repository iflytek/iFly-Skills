# Xfei Video Translation

iFlytek (讯飞) Video Translation API Skill for AI-powered video dubbing and localization.

## Overview

This Skill provides a command-line interface to iFlytek's Video Translation API:
- Create video translation tasks
- List all translation tasks

## API Information

- **Base URL**: `https://opensapi.xfyun.com/api/v1/video-translate`
- **Endpoints**:
  - `POST /tasks` - Create translation task
  - `GET /tasks` - List all tasks

## Quick Start

### 1. Install Dependencies

```bash
pip install requests
```

### 2. Create an App

1. Visit [讯飞控制台](https://console.xfyun.cn)
2. Create an app with **视频翻译** service enabled
3. Enable the desired voice(s) in the console

### 3. (Optional) Configure Your Own Credentials

The Skill comes with pre-configured API credentials. To use your own:

```bash
export IFLY_APP_ID="your_app_id"
export IFLY_API_KEY="your_api_key"
export IFLY_API_SECRET="your_api_secret"
```

> Compatibility: the old `XFEI_*` / `XFYUN_*` variables still work but are deprecated; the script prints a notice on stderr asking you to switch to `IFLY_*`.

### 4. Create a Translation Task

```bash
python3 scripts/xfei_video_translate.py --action create_task \
    --file_url "https://example.com/video.mp4" \
    --src_lang en --dest_lang zh
```

### 5. List All Tasks

```bash
python3 scripts/xfei_video_translate.py --action list_tasks
```

## Usage Examples

```bash
# English to Chinese
python3 scripts/xfei_video_translate.py --action create_task \
    --file_url "https://example.com/video.mp4" \
    --src_lang en --dest_lang zh

# Chinese to English
python3 scripts/xfei_video_translate.py --action create_task \
    --file_url "https://example.com/video.mp4" \
    --src_lang zh --dest_lang en

# Japanese to Korean
python3 scripts/xfei_video_translate.py --action create_task \
    --file_url "https://example.com/video.mp4" \
    --src_lang ja --dest_lang ko

# List all tasks
python3 scripts/xfei_video_translate.py --action list_tasks
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `--action create_task` | Submit a new video translation task |
| `--action list_tasks` | List all tasks |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `IFLY_APP_ID` | iFlytek Application ID |
| `IFLY_API_KEY` | iFlytek API Key |
| `IFLY_API_SECRET` | iFlytek API Secret |

## Requirements

- Python 3.7+
- `requests` library

## Documentation

See [SKILL.md](./SKILL.md) for detailed API documentation and parameter reference.
