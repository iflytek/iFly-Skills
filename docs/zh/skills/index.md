# 技能列表

每个技能都是仓库中一个独立的顶层目录，包含 `SKILL.md`（触发描述、API 文档、用法）、可运行的
`scripts/` 以及 `_meta.json` 元数据。

大多数技能共用同一套讯飞开放平台凭证——设置一次 `XFEI_APP_ID`、`XFEI_API_KEY`、`XFEI_API_SECRET`
即可在各技能间复用。参见 [快速开始](/zh/guide/quick-start)。

## 语音 {#speech}

| 技能 | 功能 | 目录 |
|------|------|------|
| **超拟人语音合成 (Hyper TTS)** 🎙️ | 高度拟人的文本转语音，精细控制发音人/语速/语调/音量/输出格式。 | [`ifly-hyper-tts`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-hyper-tts) |
| **声音克隆 (Voice Clone TTS)** 🗣️ | 从音频样本训练定制音色，再用克隆音色合成语音。 | [`ifly-voiceclone-tts`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-voiceclone-tts) |
| **极速语音转写 (Speed Transcription)** ⚡ | 超快音频转文字——每小时音频约 20 秒，最长支持 5 小时。中文、英文及 202+ 方言。 | [`ifly-speed-transcription`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-speed-transcription) |

## OCR 与视觉 {#ocr-vision}

| 技能 | 功能 | 目录 |
|------|------|------|
| **PDF / 图片 OCR** 📄 | 面向图片与 PDF 的通用 LLM OCR；可将文档转为 Word / Markdown。 | [`ifly-pdf-image-ocr`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-pdf-image-ocr) |
| **发票 OCR (Invoice OCR)** 🧾 | 从发票、票据、账单中提取结构化字段（增值税发票、出租车/火车票、医疗票据等）。 | [`ifly-ocr-invoice`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-ocr-invoice) |
| **图像理解 (Image Understanding)** 🖼️ | 基于星火视觉模型分析图片并回答相关问题。 | [`ifly-image-understanding`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-image-understanding) |

## 语言 {#language}

| 技能 | 功能 | 目录 |
|------|------|------|
| **机器翻译 (Machine Translation)** 🌐 | 在中、英、日、韩、法、西、德、俄、阿拉伯、泰、越等多语种间翻译文本。 | [`ifly-translate`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-translate) |
| **视频翻译 (Video Translation)** 🎬 | AI 驱动的视频翻译与配音，用于多语种视频本地化。 | [`ifly-video-translate`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-video-translate) |
| **文本纠错 (Text Proofread)** ✍️ | 检测并纠正中文文本错误——错别字、标点、语序、事实及敏感内容（27 类错误）。 | [`ifly-text-proofread`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-text-proofread) |

## 解决方案 {#solutions}

将多种能力串联为单一任务流的场景级技能。

| 技能 | 功能 | 目录 |
|------|------|------|
| **合同智能审核 (Contract Intelligence Review)** 📋 | 对扫描件/图片/双语合同进行端到端审核：OCR → 条款分析 → 风险检测 → 合规校对 → 摘要。 | [`ifly-contract-intelligence-review`](https://github.com/iflytek/iFly-Skills/tree/main/ifly-contract-intelligence-review) |

---

::: tip 缺少某项能力？
技能集合随社区共同成长。参见 [为文档站做贡献](/zh/contribute-to-docs) 与开放的
[贡献 issue](https://github.com/iflytek/iFly-Skills/issues)，来新增一个技能、用法示例或翻译。
:::
