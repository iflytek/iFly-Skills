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
| **Hyper TTS** | Ultra-realistic text-to-speech synthesis with advanced voice control. | [`ifly-hyper-tts`](./ifly-hyper-tts) |
| **Image Understanding** | Multimodal capability to analyze and understand image contents. | [`ifly-image-understanding`](./ifly-image-understanding) |
| **Invoice OCR** | Specialized OCR for extracting structured data from invoices. | [`ifly-ocr-invoice`](./ifly-ocr-invoice) |
| **PDF/Image OCR** | General optical character recognition for documents and images. | [`ifly-pdf-image-ocr`](./ifly-pdf-image-ocr) |
| **Speed Transcription** | High-speed audio transcription for voice-to-text scenarios. | [`ifly-speed-transcription`](./ifly-speed-transcription) |
| **Text Proofread** | Intelligent text proofreading, error detection, and correction. | [`ifly-text-proofread`](./ifly-text-proofread) |
| **Machine Translation** | High-quality, multi-language translation capabilities. | [`ifly-translate`](./ifly-translate) |
| **Voice Clone TTS** | Voice cloning technology for customized text-to-speech generation. | [`ifly-voiceclone-tts`](./ifly-voiceclone-tts) |

## 🛠️ Usage

Each skill is packaged in its own directory containing specific instructions, scripts, and metadata. To use a specific skill:

1. Navigate to the target skill's directory (e.g., `cd ifly-hyper-tts`).
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

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE).
