# Contributing to iFLYTEK Skills

English | [简体中文](CONTRIBUTING_zh.md)

Thanks for helping grow the iFLYTEK skills ecosystem! New skills, fixes, documentation and n8n node improvements are all welcome.

## Reporting bugs and requesting features

- Search [existing issues](https://github.com/iflytek/iFly-Skills/issues) first, then open a new one with the matching [issue template](https://github.com/iflytek/iFly-Skills/issues/new/choose).
- For bugs, name the skill (for example `iflytek-hyper-tts`), the agent or runtime you used it with, and the steps to reproduce. Never paste real API keys or secrets.
- **Do not report security vulnerabilities in public issues.** Follow [SECURITY.md](SECURITY.md) instead.

## Repository layout

| Path | Contents |
|---|---|
| `skills/<skill-name>/` | One skill per directory: `SKILL.md` (frontmatter + instructions), `README.md`, `_meta.json` (slug and version), `scripts/`, and optionally `tests/`, `references/`, `assets/` |
| `tests/` | Offline regression tests shared across skills |
| `packages/n8n-nodes-iflytek/` | The `@iflytekopensource/n8n-nodes-iflytek-skills` n8n community node package |
| `skills.sh.json` | Skill groupings for skills.sh |

## Adding or changing a skill

1. Use an existing skill such as `skills/iflytek-hyper-tts/` as a template. The directory name, the `name` in `SKILL.md` and the `slug` in `_meta.json` must match.
2. Read credentials from the standard `IFLY_APP_ID`, `IFLY_API_KEY` and `IFLY_API_SECRET` environment variables. Never commit real credentials.
3. Bump `version` in `_meta.json` when you change a published skill.
4. Add new skills to a grouping in `skills.sh.json` and to the skill tables in `README.md` and `README_zh.md`.

## Testing policy

**New functionality and bug fixes must come with automated tests.**

- Tests must run offline: mock HTTP and WebSocket calls instead of calling iFLYTEK services, so CI needs no credentials.
- When you add a skill script or a significant feature, add tests under `skills/<skill-name>/tests/` or `tests/<skill_name>/`.
- When you fix a bug, add a regression test that fails without the fix whenever practical.
- If a change cannot reasonably be tested automatically, explain why in the pull request and describe how you verified it manually.

Run the checks locally before opening a pull request:

```bash
# Python skills (same checks as the Python Check workflow)
pip install ruff websocket-client -r tests/iflytek_speed_transcription/requirements.txt
python -m compileall -q skills tests
ruff check --select=E9,F63,F7,F82 skills tests
python -m unittest discover -s tests -p 'test_skill_credentials.py'
python -m unittest discover -s tests/iflytek_speed_transcription -p 'test_*.py'
python -m unittest discover -s tests/iflytek_voiceclone_tts -p 'test_*.py'
python -m unittest discover -s skills/iflytek-hyper-tts/tests -p 'test_*.py'

# n8n package
cd packages/n8n-nodes-iflytek
npm ci && npm run typecheck && npm test
```

CI also validates every skill with [skillcheck](https://github.com/Jetty0728/skillcheck) and [skill-linter](https://www.npmjs.com/package/skill-linter), and audits the n8n package's production dependencies.

## Submitting a pull request

1. Fork the repository and create a branch from `main` (for example `feat/new-skill`).
2. Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages, e.g. `feat(hyper-tts): support mp3 output`.
3. Sign off every commit (`git commit -s`) to certify the [Developer Certificate of Origin](https://developercertificate.org/).
4. Open a pull request against `main`, describe the change and how you tested it, and make sure CI passes.
5. The CLA Assistant bot will ask first-time contributors to sign the Contributor License Agreement.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
