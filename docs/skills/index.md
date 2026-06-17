# Skill Catalog

Every skill lives in its own top-level directory in the repository. Each package contains a
`SKILL.md` (trigger description, API docs, usage), runnable `scripts/`, and `_meta.json` metadata.

Most skills share the same iFLYTEK Open Platform credentials — set `XFEI_APP_ID`, `XFEI_API_KEY`,
and `XFEI_API_SECRET` once and reuse them across skills. See the [Quick Start](/guide/quick-start)
for setup.

## Speech {#speech}

| Skill | What it does | Directory |
|-------|--------------|-----------|
| **Hyper TTS** 🎙️ | Ultra-realistic text-to-speech with fine voice control (speaker / speed / pitch / volume / output format). | [`ifly-hyper-tts`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-hyper-tts) |
| **Voice Clone TTS** 🗣️ | Train a custom voice from audio samples, then synthesize speech in that cloned voice. | [`ifly-voiceclone-tts`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-voiceclone-tts) |
| **Speed Transcription** ⚡ | Ultra-fast audio-to-text — up to 5 hours of audio in ~20s per hour. Chinese, English, and 202+ dialects. | [`ifly-speed-transcription`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-speed-transcription) |

## OCR & Vision {#ocr-vision}

| Skill | What it does | Directory |
|-------|--------------|-----------|
| **PDF / Image OCR** 📄 | General LLM-powered OCR for images and PDFs; convert documents to Word / Markdown. | [`ifly-pdf-image-ocr`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-pdf-image-ocr) |
| **Invoice OCR** 🧾 | Extract structured fields from invoices, receipts, and bills (VAT invoices, taxi/train tickets, medical bills, and more). | [`ifly-ocr-invoice`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-ocr-invoice) |
| **Image Understanding** 🖼️ | Analyze images and answer questions about them with the Spark Vision model. | [`ifly-image-understanding`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-image-understanding) |

## Language {#language}

| Skill | What it does | Directory |
|-------|--------------|-----------|
| **Machine Translation** 🌐 | Translate text across Chinese, English, Japanese, Korean, French, Spanish, German, Russian, Arabic, Thai, Vietnamese, and many more. | [`ifly-translate`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-translate) |
| **Video Translation** 🎬 | AI-powered video translation and dubbing for multilingual localization. | [`ifly-video-translate`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-video-translate) |
| **Text Proofread** ✍️ | Detect and correct Chinese text errors — typos, punctuation, word order, factual and sensitive-content issues (27 error types). | [`ifly-text-proofread`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-text-proofread) |

## Document Solutions {#solutions}

Scenario-oriented skills that chain several capabilities into one task flow.

| Skill | What it does | Directory |
|-------|--------------|-----------|
| **Contract Intelligence Review** 📋 | End-to-end contract review over scans / images / bilingual contracts: OCR → clause analysis → risk detection → compliance proofreading → summary. | [`ifly-contract-intelligence-review`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-contract-intelligence-review) |

---

::: tip Missing a capability?
The catalog grows with the community. See [Contribute to the Docs](/contribute-to-docs) and the
open [contribution issues](https://github.com/iflytek/iFly-Skills/issues) to add a skill, a usage
recipe, or a translation.
:::
