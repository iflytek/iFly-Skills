# iFly-Skills 🚀

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CLA Assistant](https://img.shields.io/badge/CLA-Assistant-green.svg)](CLA.md)

[English](README.md) | [中文](README_zh.md)

这是科大讯飞 (iFLYTEK) 面向智能体 (Agent) 生态系统和开发者工作流的官方 AI 技能 (Skills) 集合。

本仓库是一个基于科大讯飞 AI 能力构建的集中式技能库。目前它包含了基于原子模型能力的可复用技能，涵盖了语音、OCR、翻译、文本纠错和多模态理解等领域。

除了原子技能，本仓库旨在不断向更多面向场景的技能包扩展。未来，它将不仅包括单一能力的技能，还将包含面向实际业务场景的工作流级别和解决方案级别的技能，例如文档处理、内容生产、智能审核、多模态分析以及其他综合任务链。

本仓库的目标是为技能的打包、版本控制、维护和外部发布提供一个统一的平台，使科大讯飞的能力在基于智能体的生态系统中更容易被理解、安装、组合和演进。

> **⚠️ Beta** — 本项目处于活跃开发阶段。技能、API 和配置格式可能会在不另行通知的情况下发生变化。我们欢迎您的反馈和贡献。

## 📦 可用注册源

您可以从以下注册源浏览和安装技能：

| 注册源 | 地址 |
|----------|-----|
| 讯飞SkillHub (官方平台) | [skill.xfyun.cn](https://skill.xfyun.cn/search?q=ifly-&sort=relevance&page=0&starredOnly=false) |
| ClawHub | [clawhub.ai/user/iflytek.skills](https://clawhub.ai/user/iflytek.skills) |
| Skills.sh | [skills.sh/iflytek/ifly-skills](https://www.skills.sh/iflytek/ifly-skills) |
| SkillHub（腾讯云） | [skillhub.cloud.tencent.com](https://skillhub.cloud.tencent.com/skills?keyword=iflytek-&sortBy=score&source=clawhub) |
| SkillsMP | [skillsmp.com/creators/iflytek](https://skillsmp.com/zh/creators/iflytek) |
| LobeHub | [lobehub.com/skills?q=iflytek](https://lobehub.com/zh/skills?q=iflytek) |

## 🌟 现有技能列表

目前，仓库提供以下开箱即用的 AI 技能：

| 技能名称 | 功能描述 | 对应目录 |
|------------|-------------|-----------|
| **超拟人语音合成 (Hyper TTS)** | 提供高度拟人化的文本转语音合成能力，支持高级发音控制。 | [`iflytek-hyper-tts`](./skills/iflytek-hyper-tts) |
| **图像理解 (Image Understanding)** | 多模态能力，能够分析和理解图像内容。 | [`iflytek-image-understanding`](./skills/iflytek-image-understanding) |
| **发票 OCR (Invoice OCR)** | 专用的发票光学字符识别，用于提取结构化的发票数据。 | [`iflytek-ocr-invoice`](./skills/iflytek-ocr-invoice) |
| **PDF/图片 OCR (PDF/Image OCR)** | 通用的文档和图像光学字符识别。 | [`iflytek-pdf-image-ocr`](./skills/iflytek-pdf-image-ocr) |
| **极速语音转写 (Speed Transcription)** | 高速的音频转写功能，适用于语音转文本场景。 | [`iflytek-speed-transcription`](./skills/iflytek-speed-transcription) |
| **文本纠错 (Text Proofread)** | 智能文本纠错、错误检测与修正。 | [`iflytek-text-proofread`](./skills/iflytek-text-proofread) |
| **机器翻译 (Machine Translation)** | 高质量的多语种翻译能力。 | [`iflytek-translate`](./skills/iflytek-translate) |
| **视频翻译 (Video Translate)** | AI 驱动的视频翻译，支持配音与多语种本地化。 | [`iflytek-video-translate`](./skills/iflytek-video-translate) |
| **声音克隆 (Voice Clone TTS)** | 声音克隆技术，用于生成定制化的文本转语音。 | [`iflytek-voiceclone-tts`](./skills/iflytek-voiceclone-tts) |
| **合同智能审核 (Contract Intelligence Review)** | 合同智能审核，覆盖 OCR 识别、条款分析、风险检测与合规校对。 | [`iflytek-contract-intelligence-review`](./skills/iflytek-contract-intelligence-review) |
| **手绘动画架构图 (Animated Sketch Diagram)** | 手绘涂鸦风动画架构图/流程图，纯 SVG+CSS 单文件 HTML，可导出无缝循环 GIF。 | [`animated-sketch-diagram`](./skills/animated-sketch-diagram) |

## 🛠️ 如何使用

每个技能都打包在各自的独立目录中，包含特定的说明、脚本和元数据。要使用某个特定技能：

1. 进入目标技能的目录（例如：`cd skills/iflytek-hyper-tts`）。
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

为避免 Fork 场景下的 Pull Request 出现与贡献内容无关的 `signatures/version1/cla.json` 变更和合并冲突，CLA 签名信息会存储在独立的远端签名仓库中，而不是回写到当前代码仓库。

**维护者配置：** 请在仓库中设置变量 `CLA_SIGNATURE_STORE_ORG`、`CLA_SIGNATURE_STORE_REPO`，可选变量 `CLA_SIGNATURE_STORE_BRANCH`，以及带有远端签名仓库写权限的仓库密钥 `CLA_SIGNATURE_STORE_PAT`。用于存储签名的分支不应启用保护。

## 📄 许可证

本项目基于 [Apache License 2.0](LICENSE) 协议开源。

## 💬 社区交流

欢迎加入 Astron 开源交流群（企业微信），与我们交流与合作：

<img src="https://github.com/iflytek/astron-agent/raw/main/docs/imgs/WeCom_Group.png" alt="加入 Astron 开源交流群" width="300" />
