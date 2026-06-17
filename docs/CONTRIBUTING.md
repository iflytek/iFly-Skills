# Contributing Guide

We welcome contributions to expand the iFLYTEK skills ecosystem! There are several ways to help —
pick whichever fits your time and interest.

## Ways to contribute

| Contribution | Good first step |
|--------------|-----------------|
| **Add a new skill** | Package an iFLYTEK capability as a self-contained skill directory. |
| **Add a usage recipe** | Show a real task solved with one or more existing skills. |
| **Translate the docs** | Mirror an English page under a new language folder (`docs/<lang>/`). |
| **Expand the FAQ** | Add a question + answer you wish had existed when you started. |
| **Report or fix bugs** | Open an issue, or send a PR with the fix. |

Open [issues labeled **good first issue** / **help wanted**](https://github.com/iflytek/iFly-Skills/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22%2C%22help+wanted%22)
are the easiest places to start.

## Adding a new skill

Each skill is a self-contained top-level directory:

```
ifly-<your-skill>/
├── SKILL.md        # required: frontmatter (name, description, metadata) + API docs & usage
├── scripts/        # runnable scripts; prefer the Python standard library
└── _meta.json      # metadata
```

1. Use an existing skill (e.g. [`ifly-translate`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-translate))
   as a template.
2. Write a clear `SKILL.md`: the frontmatter `description` and `user_instructions` decide *when* an
   agent triggers the skill; the body documents *how* to call it.
3. **Never commit credentials.** Read `XFEI_APP_ID` / `XFEI_API_KEY` / `XFEI_API_SECRET` from the
   environment; use placeholders in examples.
4. Add your skill to the [Skill Catalog](/skills/) and the repository README tables.

## General workflow

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/new-skill`).
3. Commit your changes (`git commit -m 'feat: add awesome new skill'`).
4. Push the branch and open a Pull Request.

### Contributor License Agreement (CLA)

When you open a Pull Request, the **CLA Assistant** bot will ask you to sign the
[Contributor License Agreement](https://github.com/iflytek/iFly-Skills/blob/main/CLA.md). Follow the
bot's instructions to complete the PR. CLA signatures are stored in a dedicated remote signature
repository, so you won't see unrelated signature diffs in your PR.

## Improving the docs

This site is built with [VitePress](https://vitepress.dev/). See
[Contribute to the Docs](/contribute-to-docs) for how to run it locally, where pages live, and how to
add a new language.

## Community

Join the Astron Open Source Community (WeCom Group) — the QR code is in the repository
[README](https://github.com/iflytek/iFly-Skills#-community).
