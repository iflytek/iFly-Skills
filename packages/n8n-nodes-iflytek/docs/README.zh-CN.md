# @iflytekopensource/iFLYTEK Skills

**npm 包名：** `@iflytekopensource/n8n-nodes-iflytek-skills`

中文 · [English](../README.md)

本文为中文概述；完整安装步骤及英文用户文档见 [默认 README](../README.md)。

将 iFLYTEK Skills 接入自托管 n8n，为工作流提供语音、图像与文档处理、多语言理解和翻译能力。远端服务使用共享的 **iFlytek API** 凭证，Skill 通过本机 Python 执行。

## 支持的节点

本包提供 11 个节点、25 个操作。各操作的输入输出、使用方式和限制见 [节点参考](nodes.md)。

| 节点 | 能力 |
| --- | --- |
| iFlytek Translate | 文本翻译 |
| iFlytek Text Proofread | 中文文本校对 |
| iFlytek Invoice OCR | 发票、收据等票据识别 |
| iFlytek Hyper TTS | 语音合成；查看随包静态音色列表 |
| iFlytek PDF and Image OCR | 图片 OCR；创建和查询 PDF OCR 任务 |
| iFlytek Speed Transcription | 创建和查询 MP3 转写任务 |
| iFlytek Image Understanding | 图片内容理解与问答 |
| iFlytek Video Translate | 创建、查询和管理视频翻译任务 |
| iFlytek Voice Clone TTS | 声音训练与克隆语音合成 |
| iFlytek Contract Review | 审核文本及文档合同，生成 Markdown 和 JSON 报告 |
| iFlytek Animated Sketch | 将受限 HTML/SVG/CSS 渲染为 GIF |

## 安装

在 n8n 的 **Settings → Community Nodes → Install** 中输入完整包名 `@iflytekopensource/n8n-nodes-iflytek-skills`，或在实例的社区节点目录（默认 `~/.n8n/nodes`）执行：

```sh
npm install --save-exact @iflytekopensource/n8n-nodes-iflytek-skills@VERSION
```

将 `VERSION` 替换为已发布版本号。按 [安装与配置](installation.md) 准备 Python 依赖，设置解释器和临时目录，运行预检并重启 n8n。npm 安装不会自动配置 Python。使用旧开发包名创建的工作流需按 [迁移说明](installation.md#migrating-existing-test-workflows) 更新节点类型。

## 最小示例

1. 创建 **iFlytek API** 凭证，填写同一讯飞应用的 **App ID**、**API Key** 和 **API Secret**；应用需开通翻译服务并有可用额度。
2. 在节点选择器中搜索 `iFlytek`，连接 **Manual Trigger → iFlytek Translate**，选择上述凭证。
3. 将 **Text** 设为“欢迎使用 iFLYTEK Skills”，**Source Language** 设为 `cn`，**Target Language** 设为 `en`，执行节点。

译文位于 `data.translatedText`，下游可使用 `{{ $json.data.translatedText }}`。此示例会调用收费翻译服务。其他节点的业务结果位于 `json.data`，文件通过 n8n binary 字段传递；详细约定见 [输入、结果与错误处理](operations.md#inputs-results-and-errors)。

## 运行要求

- **本包当前支持 Node.js 24.x**（`>=24.0.0 <25`）。已验证的 n8n 版本与各自的 Node.js 要求见 [兼容范围](compatibility.md)。
- **Python 3.10 或更高版本**，使用独立 venv 安装随包锁定依赖；合同文档处理使用 full 依赖。
- **自托管 n8n**，允许启动本地子进程并写入临时目录。手绘图另需浏览器及 ffmpeg；具体配置见 [安装指南](installation.md)。
- **讯飞服务授权**：远端操作需要应用的 App ID、API Key、API Secret，以及各项服务的授权和可用额度。

## 文档与反馈

- [安装与配置](installation.md)、[兼容范围](compatibility.md)。
- [节点参考](nodes.md)、[可导入的示例工作流](workflows.md)。
- [运行、错误处理与恢复](operations.md)、[版本记录](../CHANGELOG.md)。
- [问题反馈](https://github.com/iflytek/iFly-Skills/issues/new?template=n8n-node.yml)：附版本、节点操作、错误码及脱敏复现，不公开凭证或业务原文。
- [贡献指南](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/CONTRIBUTING.md)。

## 使用限制

- 本包依赖本地 Python 子进程，不支持 n8n Cloud。`n8n-community-node-package` 关键词供 npm 检索使用，不代表 n8n 官方认证或已验证节点目录收录。
- 共享凭证仍需分别开通各项远端服务及额度。静态音色列表和本地手绘图不调用 API；语音合成需要服务授权。
- 远端操作会将输入的文本、文件或 URL 发送至讯飞服务；Python 在本地执行不代表这些操作可离线完成。
- 合同审核结果需人工复核；手绘图渲染现成 HTML，不从自然语言生成图表。收费任务的重试与恢复方式见 [运行指南](operations.md#long-running-tasks-duplicate-charges-and-worker-recovery)。

## 许可

本包使用 [Apache-2.0](../LICENSE)。手绘图适配保留 [MIT 许可](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/licenses/animated-sketch-diagram-MIT.txt)，Kalam 字体使用 [SIL OFL 1.1](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/licenses/Kalam-OFL.txt)，两份许可均随包保存在 `runtime/bridge/diagram/licenses/`。浏览器、ffmpeg 及其他依赖遵循各自许可。
