# Changelog

Release notes for `@iflytekopensource/n8n-nodes-iflytek-skills`.

## Unreleased

- Moved the Chinese overview to `docs/README.zh-CN.md` so npm selects the English `README.md` for the package page.

## 0.1.0

- Packaged as the public scoped package `@iflytekopensource/n8n-nodes-iflytek-skills`, with installation instructions and workflow examples using the full package name.
- Added 11 n8n nodes covering 25 operations for iFLYTEK speech, OCR, translation, proofreading, image understanding, contract review, and local HTML diagram rendering.
- Added the shared iFlytek API credential and isolated Python execution with binary input/output, cancellation, timeouts, bounded concurrency, and controlled error reporting.
- Bundled fixed Skill snapshots, Python dependency locks, runtime integrity metadata, and license notices.
- Added installation, compatibility, and recovery guidance, plus three importable workflows for proofreading/translation, invoice OCR, and speech synthesis.
- Provided the default README and user guides in English, with a Chinese overview in `README.zh-CN.md`.
