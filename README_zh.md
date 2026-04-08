# iFly-Skills 🚀

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CLA Assistant](https://img.shields.io/badge/CLA-Assistant-green.svg)](CLA.md)

[English](README.md) | [中文](README_zh.md)

这是科大讯飞 (iFLYTEK) 面向智能体 (Agent) 生态系统和开发者工作流的官方 AI 技能 (Skills) 集合。

本仓库是一个基于科大讯飞 AI 能力构建的集中式技能库。目前它包含了基于原子模型能力的可复用技能，涵盖了语音、OCR、翻译、文本纠错和多模态理解等领域。

除了原子技能，本仓库旨在不断向更多面向场景的技能包扩展。未来，它将不仅包括单一能力的技能，还将包含面向实际业务场景的工作流级别和解决方案级别的技能，例如文档处理、内容生产、智能审核、多模态分析以及其他综合任务链。

本仓库的目标是为技能的打包、版本控制、维护和外部发布提供一个统一的平台，使科大讯飞的能力在基于智能体的生态系统中更容易被理解、安装、组合和演进。

## 🌟 现有技能列表

目前，仓库提供以下开箱即用的 AI 技能：

| 技能名称 | 功能描述 | 对应目录 |
|------------|-------------|-----------|
| **超拟人语音合成 (Hyper TTS)** | 提供高度拟人化的文本转语音合成能力，支持高级发音控制。 | [`ifly-hyper-tts`](./ifly-hyper-tts) |
| **图像理解 (Image Understanding)** | 多模态能力，能够分析和理解图像内容。 | [`ifly-image-understanding`](./ifly-image-understanding) |
| **发票 OCR (Invoice OCR)** | 专用的发票光学字符识别，用于提取结构化的发票数据。 | [`ifly-ocr-invoice`](./ifly-ocr-invoice) |
| **PDF/图片 OCR (PDF/Image OCR)** | 通用的文档和图像光学字符识别。 | [`ifly-pdf-image-ocr`](./ifly-pdf-image-ocr) |
| **极速语音转写 (Speed Transcription)** | 高速的音频转写功能，适用于语音转文本场景。 | [`ifly-speed-transcription`](./ifly-speed-transcription) |
| **文本纠错 (Text Proofread)** | 智能文本纠错、错误检测与修正。 | [`ifly-text-proofread`](./ifly-text-proofread) |
| **机器翻译 (Machine Translation)** | 高质量的多语种翻译能力。 | [`ifly-translate`](./ifly-translate) |
| **声音克隆 (Voice Clone TTS)** | 声音克隆技术，用于生成定制化的文本转语音。 | [`ifly-voiceclone-tts`](./ifly-voiceclone-tts) |

## 🛠️ 如何使用

每个技能都打包在各自的独立目录中，包含特定的说明、脚本和元数据。要使用某个特定技能：

1. 进入目标技能的目录（例如：`cd ifly-hyper-tts`）。
2. 阅读目录下的 `SKILL.md` 文件，获取详细的 API 文档、所需的环境变量（如 `XFEI_APP_ID`, `XFEI_API_KEY`, `XFEI_API_SECRET`）以及使用示例。
3. 使用提供的 Python 脚本，或者将该能力集成到您自己的智能体工作流中。

## 🤝 参与贡献

我们非常欢迎您参与贡献，共同扩展科大讯飞的技能生态！

1. Fork 本仓库。
2. 创建您的特性分支 (`git checkout -b feature/new-skill`)。
3. 提交您的修改 (`git commit -m 'feat: add awesome new skill'`)。
4. 推送至分支 (`git push origin feature/new-skill`)。
5. 提交一个 Pull Request。

**注意：** 当您提交 Pull Request 时，我们的 CLA Assistant 机器人会自动要求您签署 [贡献者许可协议 (CLA)](CLA.md)。请按照机器人的提示完成 PR 流程。

## 📄 许可证

本项目基于 [Apache License 2.0](LICENSE) 协议开源。
