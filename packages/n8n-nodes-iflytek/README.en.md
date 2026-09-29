# @iflytekopensource/n8n-nodes-iflytek

[中文](README.md) · English

iFLYTEK Skills for self-hosted n8n workflows, covering speech, images and documents, and multilingual processing. Remote services share an **iFlytek API** credential; Skills execute through local Python processes.

## Supported nodes

The package provides 11 nodes and 25 operations. See the [node reference](docs/nodes.md) for operation details (Chinese).

| Node | Capabilities |
| --- | --- |
| iFlytek Translate | Translate text |
| iFlytek Text Proofread | Proofread Chinese text |
| iFlytek Invoice OCR | Recognize invoice images or PDFs |
| iFlytek Hyper TTS | Synthesize speech; inspect bundled voice constants |
| iFlytek PDF and Image OCR | Recognize images; create and query PDF tasks |
| iFlytek Speed Transcription | Create and query MP3 transcription tasks |
| iFlytek Image Understanding | Answer questions about an image |
| iFlytek Video Translate | Create, query, and manage video translation tasks |
| iFlytek Voice Clone TTS | Train voices and synthesize cloned speech |
| iFlytek Contract Review | Review text or document contracts and return reports |
| iFlytek Animated Sketch | Render restricted HTML/SVG/CSS to GIF |

## Installation

Enter `@iflytekopensource/n8n-nodes-iflytek` in **Settings → Community Nodes → Install**, or run this command in your instance's community-node directory (normally `~/.n8n/nodes`):

```sh
npm install --save-exact @iflytekopensource/n8n-nodes-iflytek@VERSION
```

Replace `VERSION` with a published version. Follow the [installation guide](docs/installation.md) (Chinese) to prepare Python dependencies, configure the interpreter and temporary directory, run preflight, and restart n8n. npm installation does not configure Python. Existing workflows using the unscoped package name need the [migration procedure](docs/installation.md#迁移已有测试工作流).

## Minimal example

1. Create an **iFlytek API** credential using the **App ID**, **API Key**, and **API Secret** from one application with translation access and available quota.
2. Search for `iFlytek` in the node selector, connect **Manual Trigger → iFlytek Translate**, and select the credential.
3. Set **Text** to `欢迎使用 iFLYTEK Skills`, **Source Language** to `cn`, and **Target Language** to `en`, then execute the node.

Read the translation from `data.translatedText`, or use `{{ $json.data.translatedText }}` downstream. This example calls a paid translation service. Other node results are in `json.data`; files use n8n binary properties. See [input, result, and error behavior](docs/operations.md#输入结果与错误处理) for details (Chinese).

## Requirements

- **This package currently supports Node.js 24.x** (`>=24.0.0 <25`). Tested n8n versions and their Node.js requirements are listed in the [compatibility guide](docs/compatibility.md).
- **Python 3.10 or newer**, with the bundled locked dependencies in a dedicated virtual environment. Contract document processing uses the full dependency profile.
- **Self-hosted n8n** with permission to launch local child processes and write temporary files. Diagram rendering also requires a browser and ffmpeg; see the [installation guide](docs/installation.md).

## Documentation and support

- [Installation](docs/installation.md) and [compatibility](docs/compatibility.md) (Chinese).
- [Node reference](docs/nodes.md) and [importable example workflows](docs/workflows.md) (Chinese).
- [Operations, errors, and recovery](docs/operations.md) (Chinese), and the [package changelog](CHANGELOG.md).
- [Report an issue](https://github.com/iflytek/iFly-Skills/issues/new?template=n8n-node.yml) with versions, node/operation, error code, and a sanitized reproduction. Never post credentials or private documents.
- [Contributor guide](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/CONTRIBUTING.md) (Chinese).

## Limitations

- Local Python execution requires a self-hosted instance; n8n Cloud is not supported. The `n8n-community-node-package` keyword enables npm indexing, not n8n verified status or verified-node catalogue inclusion.
- Shared credentials still need authorization and quota for each remote service. Local diagram rendering and bundled voice listing do not call an API; speech synthesis requires service access.
- Contract results require human review. Animated Sketch renders existing HTML, not natural-language diagram requests. See the [operations guide](docs/operations.md#长任务重复费用与-worker-恢复) before retrying or recovering paid tasks.

## License

The package is [Apache-2.0](LICENSE). The diagram adaptation retains its [MIT notice](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/licenses/animated-sketch-diagram-MIT.txt); the bundled Kalam font is covered by [SIL OFL 1.1](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/licenses/Kalam-OFL.txt). Both notices are included in `runtime/bridge/diagram/licenses/`. Browsers, ffmpeg, and other dependencies retain their respective licenses.
