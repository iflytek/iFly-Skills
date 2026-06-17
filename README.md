# iFly-Skills 🚀

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CLA Assistant](https://img.shields.io/badge/CLA-Assistant-green.svg)](CLA.md)

[English](README.md) | [中文](README_zh.md)

Official collection of iFLYTEK skills for agent ecosystems and developer workflows.

This repository serves as a centralized skill collection built on top of iFLYTEK AI capabilities. It currently includes reusable skills based on atomic model abilities such as speech, OCR, translation, proofreading, and multimodal understanding.

Beyond atomic skills, this repository is designed to continuously expand toward more scenario-oriented skill packages. In the future, it will include not only single-capability skills, but also workflow-level and solution-level skills for real business scenarios, such as document processing, content production, intelligent review, multimodal analysis, and other integrated task chains.

The goal of this repository is to provide a unified place for skill packaging, versioning, maintenance, and external distribution, making iFLYTEK capabilities easier to understand, install, combine, and evolve in agent-based ecosystems.

## 🌟 Available Skills

Currently, the repository provides the following ready-to-use AI skills:

| Skill Name | Description | Directory |
|------------|-------------|-----------|
| **Hyper TTS** | Ultra-realistic text-to-speech synthesis with advanced voice control. | [`iflytek-hyper-tts`](./skills/iflytek-hyper-tts) |
| **Image Understanding** | Multimodal capability to analyze and understand image contents. | [`iflytek-image-understanding`](./skills/iflytek-image-understanding) |
| **Invoice OCR** | Specialized OCR for extracting structured data from invoices. | [`iflytek-ocr-invoice`](./skills/iflytek-ocr-invoice) |
| **PDF/Image OCR** | General optical character recognition for documents and images. | [`iflytek-pdf-image-ocr`](./skills/iflytek-pdf-image-ocr) |
| **Speed Transcription** | High-speed audio transcription for voice-to-text scenarios. | [`iflytek-speed-transcription`](./skills/iflytek-speed-transcription) |
| **Text Proofread** | Intelligent text proofreading, error detection, and correction. | [`iflytek-text-proofread`](./skills/iflytek-text-proofread) |
| **Machine Translation** | High-quality, multi-language translation capabilities. | [`iflytek-translate`](./skills/iflytek-translate) |
| **Video Translate** | AI-powered video translation with dubbing and multilingual localization. | [`iflytek-video-translate`](./skills/iflytek-video-translate) |
| **Voice Clone TTS** | Voice cloning technology for customized text-to-speech generation. | [`iflytek-voiceclone-tts`](./skills/iflytek-voiceclone-tts) |
| **Contract Intelligence Review** | Intelligent contract review covering OCR, clause analysis, risk detection, and compliance. | [`iflytek-contract-intelligence-review`](./skills/iflytek-contract-intelligence-review) |

## 🛠️ Usage

Each skill is packaged in its own directory containing specific instructions, scripts, and metadata. To use a specific skill:

1. Navigate to the target skill's directory (e.g., `cd skills/iflytek-hyper-tts`).
2. Read the `SKILL.md` file for detailed API documentation, required environment variables (e.g., `XFEI_APP_ID`, `XFEI_API_KEY`, `XFEI_API_SECRET`), and usage examples.
3. Use the provided Python scripts or integrate the capability into your own agent workflow.

## 🤝 Contributing

We welcome contributions to expand the iFLYTEK skills ecosystem!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/new-skill`).
3. Commit your changes (`git commit -m 'feat: add awesome new skill'`).
4. Push to the branch (`git push origin feature/new-skill`).
5. Open a Pull Request.

**Note:** When you submit a Pull Request, our CLA Assistant bot will automatically ask you to sign the [Contributor License Agreement (CLA)](CLA.md). Please follow the bot's instructions to complete the PR process.

To avoid unrelated `signatures/version1/cla.json` diffs and merge conflicts in fork-based Pull Requests, CLA signatures are stored in a dedicated remote signature repository instead of this codebase.

**Maintainer setup:** configure repository variables `CLA_SIGNATURE_STORE_ORG`, `CLA_SIGNATURE_STORE_REPO`, and optional `CLA_SIGNATURE_STORE_BRANCH`, plus repository secret `CLA_SIGNATURE_STORE_PAT` with write access to the remote signature repository. The branch used to store signatures should not be protected.

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE).

## 💬 Community

Join the Astron Open Source Community (WeCom Group) to discuss and collaborate:

<img src="https://github.com/iflytek/astron-agent/raw/main/docs/imgs/WeCom_Group.png" alt="WeCom Group" width="300" />
