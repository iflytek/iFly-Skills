---
name: iflytek-screenshot-to-code
description: Convert a UI screenshot or mockup into a single HTML, React, or Vue source file with an Astron MaaS vision model. Use for screenshot-to-code and image-to-frontend requests; do not use for general image description or for editing an existing codebase without a screenshot.
metadata: {
  "homepage": "https://www.xfyun.cn/doc/spark/%E5%9B%BE%E5%83%8F%E7%90%86%E8%A7%A3API-http.html",
  "openclaw": "{\"emoji\":\"🖼️\",\"dimensions\":[\"截图转代码\",\"前端界面复刻\"],\"user_instructions\":[\"把这张截图转成 HTML\",\"根据这个 UI 截图生成 React 页面\",\"复刻这张网页截图\"],\"requires\":{\"bins\":[\"python3\"],\"env\":[\"IFLYTEK_MAAS_API_KEY\",\"IFLYTEK_MAAS_MODEL_ID\"]},\"primaryEnv\":\"IFLYTEK_MAAS_API_KEY\"}"
}
---

# iFLYTEK Screenshot to Code

Generate one frontend source file from a PNG, JPEG, or WebP screenshot through an Astron MaaS vision model.

## Prerequisites

Set credentials from the MaaS service card that owns a vision-capable model:

```bash
export IFLYTEK_MAAS_API_KEY="your-api-key"
export IFLYTEK_MAAS_MODEL_ID="your-vision-model-id"
```

The script defaults to the current MaaS v2 base URL. If the service card shows another URL, set `IFLYTEK_MAAS_BASE_URL` to that base URL. Never put the API key in prompts, source files, or command-line flags.

## Generate

Choose the stack from the user's request. Default to `html-css` when they only ask for a runnable page.

```bash
python3 scripts/screenshot_to_code.py screenshot.png \
  --stack html-css \
  --output generated.html
```

Supported single-file contracts:

| Stack | Output |
|---|---|
| `html-css` | Complete HTML document with embedded CSS (`.html`) |
| `react-tailwind` | Default-exported React component (`.jsx`) |
| `vue-tailwind` | Vue single-file component (`.vue`) |

Pass concrete user requirements without rewriting the base fidelity prompt:

```bash
python3 scripts/screenshot_to_code.py dashboard.webp \
  --stack react-tailwind \
  --instructions "Make the sidebar collapsible and preserve the mobile layout." \
  --output Dashboard.jsx
```

The command refuses to overwrite an existing file. Use `--force` only when the user has asked to replace it.

## Verify

After generation:

1. Read the generated file and reject unsafe or unrelated behavior before running it.
2. Render it with the project's normal frontend tooling when available.
3. Compare layout, text, spacing, color, and responsive structure with the screenshot.
4. Fix small deterministic defects in the generated source. Make another paid MaaS call only when a concrete visual failure cannot be corrected locally.

The script accepts raw code or one exact Markdown code block. It refuses mixed prose, incomplete HTML, React without a default export, and malformed Vue single-file output.

## Limits

- One screenshot and one source file per invocation.
- Input must be PNG, JPEG, or WebP and no larger than 10 MiB.
- Generated React/Vue files assume the destination project already provides the named framework and Tailwind.
- Model output can be inaccurate. Treat it as generated source that still requires review.

## Credits

The workflow is inspired by the MIT-licensed [abi/screenshot-to-code](https://github.com/abi/screenshot-to-code) project. This skill is an independent Astron MaaS client and does not vendor upstream code.
