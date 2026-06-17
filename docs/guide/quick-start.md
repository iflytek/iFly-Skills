# Quick Start

This guide gets you from zero to running your first iFly-Skill in a few minutes.

## 1. Prerequisites

- **Python 3** (most skills depend only on the standard library — no `pip install` needed).
- An **iFLYTEK Open Platform** account: <https://www.xfyun.cn/>.

## 2. Get your credentials

1. Sign in to the [iFLYTEK Open Platform console](https://console.xfyun.cn/).
2. Create an application, then open the capability you want to use (e.g. *Speech Synthesis*,
   *General OCR*, *Machine Translation*). Some capabilities must be enabled per-application.
3. From the application page, copy its **APPID**, **APIKey**, and **APISecret**.

> Each capability may have its own activation and quota. If a skill returns an authorization error,
> confirm that the corresponding service is enabled for your application.

## 3. Set environment variables

The skills read credentials from the environment. Set them once and reuse across skills:

::: code-group

```bash [macOS / Linux]
export XFEI_APP_ID="your_app_id"
export XFEI_API_KEY="your_api_key"
export XFEI_API_SECRET="your_api_secret"
```

```powershell [Windows PowerShell]
$env:XFEI_APP_ID = "your_app_id"
$env:XFEI_API_KEY = "your_api_key"
$env:XFEI_API_SECRET = "your_api_secret"
```

:::

## 4. Get the skill

Clone the repository (or copy the single skill directory you need):

```bash
git clone https://github.com/iflytek/iFly-Skills.git
cd iFly-Skills
```

## 5. Run a skill

Every skill documents its exact commands in its own `SKILL.md`. The general pattern is:

```bash
cd ifly-hyper-tts          # pick a skill directory
cat SKILL.md               # read its API docs and usage examples
python3 scripts/...        # run the script described there
```

Browse the full list on the [Skill Catalog](/skills/) page and open each skill's `SKILL.md` for its
specific parameters and examples.

## 6. Use inside an agent

Because each skill is a self-contained package with a trigger description, it can be dropped into an
agent runtime that supports skills. The `SKILL.md` frontmatter (`description`, `user_instructions`)
tells the agent when to invoke the skill; the body tells it how. Point your agent at the skill
directory and it can call the scripts directly.

## Troubleshooting

See the [FAQ](/faq) for common credential, quota, and environment pitfalls.
