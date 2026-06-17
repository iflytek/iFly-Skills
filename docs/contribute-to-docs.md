# Contribute to the Docs

This documentation site is built with [VitePress](https://vitepress.dev/) and lives in the
[`docs/`](https://github.com/iflytek/iFly-Skills/tree/main/docs) folder. Improving the docs — fixing a
typo, clarifying a page, adding an FAQ entry, or translating a page into a new language — is one of
the highest-impact, lowest-barrier ways to contribute.

## Run the site locally

```bash
cd docs
npm install
npm run docs:dev
```

VitePress prints a local URL (default <http://localhost:5173>). Edits hot-reload as you save.

To reproduce the production build:

```bash
npm run docs:build
npm run docs:preview
```

## Where pages live

```
docs/
├── .vitepress/
│   └── config.mts          # site config: nav, sidebar, locales
├── index.md                # English home page
├── guide/                  # overview, quick start
├── skills/                 # skill catalog
├── faq.md                  # FAQ
├── CONTRIBUTING.md
├── contribute-to-docs.md   # this page
└── zh/                     # 简体中文 mirror (same relative paths)
    ├── index.md
    ├── guide/
    └── ...
```

Every page has an **"Edit this page on GitHub"** link at the bottom for a one-click start.

## Internationalization (i18n)

The site uses VitePress's standard i18n layout: **English is the default at the root, and each
language mirrors it under its own folder.** Simplified Chinese already lives under
[`docs/zh/`](https://github.com/iflytek/iFly-Skills/tree/main/docs/zh).

To translate a page, create the same relative path under your language folder. For example, the
Japanese quick-start mirrors the English one:

```
docs/guide/quick-start.md      →  docs/ja/guide/quick-start.md
docs/faq.md                    →  docs/ja/faq.md
```

You don't have to translate everything at once — a single page is a perfectly good first
contribution. Good first targets are `index`, `guide/quick-start`, and `faq`.

### Registering a new language

A new language also needs a one-time `locales` entry in
[`docs/.vitepress/config.mts`](https://github.com/iflytek/iFly-Skills/blob/main/docs/.vitepress/config.mts).
Copy the existing `zh` block, change the folder key (`ja`, `ko`, `es`, `fr`, …), `label`, `lang`,
`link`, and translate the `nav` / `sidebar` text. If you'd rather just translate Markdown and let a
maintainer wire up the config, say so in your PR and we'll help.

## Submitting

1. Fork the repo and create a branch.
2. Make your edits under `docs/`.
3. Build locally (`npm run docs:build`) to catch any errors.
4. Open a Pull Request. The CLA Assistant bot will guide you through signing the CLA.

Thanks for helping more developers use iFly-Skills in their own language! 🙌
