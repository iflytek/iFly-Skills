# iFLYTEK Screenshot to Code

Turns a UI screenshot into a single frontend source file with an Astron MaaS vision model. The bundled Python client has no third-party runtime dependencies and calls the OpenAI-compatible `/chat/completions` API.

## Setup

Create or publish a vision-capable service in Astron MaaS, then copy the API key, model ID, and API base URL from its service card.

```bash
export IFLYTEK_MAAS_API_KEY="your-api-key"
export IFLYTEK_MAAS_MODEL_ID="your-vision-model-id"
# Optional when your service card differs from the v2 default:
export IFLYTEK_MAAS_BASE_URL="https://maas-api.cn-huabei-1.xf-yun.com/v2"
```

## Usage

```bash
# Self-contained HTML and CSS
python3 scripts/screenshot_to_code.py screenshot.png \
  --output generated.html

# React + Tailwind single-file component
python3 scripts/screenshot_to_code.py screenshot.png \
  --stack react-tailwind \
  --instructions "The navigation should collapse on mobile." \
  --output ScreenshotPage.jsx

# Vue + Tailwind single-file component
python3 scripts/screenshot_to_code.py screenshot.webp \
  --stack vue-tailwind \
  --output ScreenshotPage.vue
```

The script validates the input's file signature, sends it as a base64 data URL, normalizes one exact Markdown code block when necessary, checks the selected single-file contract, and writes through an atomic temporary file. Existing output is preserved unless `--force` is explicit.

Run offline tests from this skill directory:

```bash
python3 -m unittest discover -s tests -v
```

## References

- [Astron MaaS image-understanding HTTP API](https://www.xfyun.cn/doc/spark/%E5%9B%BE%E5%83%8F%E7%90%86%E8%A7%A3API-http.html)
- [abi/screenshot-to-code](https://github.com/abi/screenshot-to-code) — product and workflow inspiration (MIT)
