# FAQ

A growing list of questions people hit when getting started. Missing one? Help us expand it — see
[Contribute to the Docs](/contribute-to-docs).

## What credentials do I need?

Most skills use the iFLYTEK Open Platform triplet: `XFEI_APP_ID`, `XFEI_API_KEY`, and
`XFEI_API_SECRET`. You create an application in the [console](https://console.xfyun.cn/) and copy its
APPID / APIKey / APISecret. See the [Quick Start](/guide/quick-start#2-get-your-credentials).

## I get an authorization or "service not enabled" error

Each capability (TTS, OCR, translation, …) may need to be **activated separately** for your
application, and each has its own quota. Open the specific capability in the console and confirm it is
enabled for the application whose APPID you are using.

## Do I need to install dependencies?

Most skills are written against the Python **standard library** only, so there is nothing to `pip
install`. If a particular skill needs extra packages, its `SKILL.md` says so.

## Where do I put my credentials?

In environment variables, not in code. The skills read `XFEI_APP_ID` / `XFEI_API_KEY` /
`XFEI_API_SECRET` from the environment. Never commit credentials to a fork or paste them into an
issue or PR.

## How do I know how to call a specific skill?

Open that skill's `SKILL.md`. The frontmatter describes when to use it; the body documents the exact
scripts, parameters, and example commands. The [Skill Catalog](/skills/) links to each one.

## Which skill should I use for my task?

- Read an image or PDF → **PDF / Image OCR**; structured invoice fields → **Invoice OCR**.
- Turn text into speech → **Hyper TTS**; clone a specific voice first → **Voice Clone TTS**.
- Transcribe audio → **Speed Transcription**.
- Translate text → **Machine Translation**; translate/dub a video → **Video Translation**.
- Proofread Chinese text → **Text Proofread**.
- Review a whole contract end-to-end → **Contract Intelligence Review**.

## Can I use these skills inside my own agent?

Yes. Each skill is a self-contained package with a trigger description, so it can be registered in an
agent runtime that supports skills, or its scripts can be called directly from your own workflow.

## How do I contribute?

Add a skill, a usage recipe, a translation, or an FAQ entry — see the [Contributing
Guide](/CONTRIBUTING) and the open [contribution issues](https://github.com/iflytek/iFly-Skills/issues).
