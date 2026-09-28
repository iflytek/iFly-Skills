# n8n-nodes-iflytek

[中文](README.md) · English

iFLYTEK Skills for self-hosted n8n: 11 nodes and 25 operations for speech, document and image processing, multilingual workflows, contract review, and local diagram rendering.

## Installation

Use Node.js 24, Python 3.10 or newer, and a self-hosted n8n instance that allows local child processes. n8n 2.39.8, 2.40.5, and 2.40.7 have been tested. n8n Cloud is not supported by this execution model.

Install an available registry version of `n8n-nodes-iflytek` through **Settings → Community Nodes**, or run `npm install --save-exact n8n-nodes-iflytek@VERSION` in your instance's community-node directory. Administrators must separately prepare a Python virtual environment:

```sh
python3 -m venv /absolute/path/iflytek-venv
/absolute/path/iflytek-venv/bin/python -m pip install \
  -r /absolute/path/node_modules/n8n-nodes-iflytek/runtime/requirements/requirements-core.lock
export IFLYTEK_PYTHON_EXECUTABLE=/absolute/path/iflytek-venv/bin/python
export IFLYTEK_TMP_ROOT=/absolute/path/writable-temporary-directory
node /absolute/path/node_modules/n8n-nodes-iflytek/dist/shared/preflight.js
```

Create the temporary directory and apply these variables to the actual n8n service and every worker. Restart n8n after installation. For contract document processing, install `requirements-full.lock` instead; it includes the core dependencies. Diagram rendering also requires an administrator-installed Chromium browser and ffmpeg, configured with `IFLYTEK_CHROME_EXECUTABLE` and `IFLYTEK_FFMPEG_EXECUTABLE`. Linux rendering keeps the Chromium sandbox enabled and requires a compatible non-root environment.

## Credentials and nodes

Create an **iFlytek API** credential with the **App ID**, **API Key**, and **API Secret** from one application. Credentials can be shared across remote nodes, but each service, voice, model, and resource needs its own authorization and quota. Local diagram rendering and `listVoices` do not contact an API; speech synthesis does require credentials.

| Node | Operations |
| --- | --- |
| iFlytek Translate | Translate text |
| iFlytek Text Proofread | Proofread Chinese text |
| iFlytek Invoice OCR | Recognize invoice images or PDFs |
| iFlytek Hyper TTS | Synthesize speech; inspect bundled voice constants |
| iFlytek PDF and Image OCR | Recognize images; create and query PDF tasks |
| iFlytek Speed Transcription | Create and query MP3 transcription tasks |
| iFlytek Image Understanding | Answer a question about an image |
| iFlytek Video Translate | Create, list, query, and confirm video tasks |
| iFlytek Voice Clone TTS | Retrieve training text; create, upload, submit, and query training; synthesize |
| iFlytek Contract Review | Review text or PDF/DOCX/image documents and return reports |
| iFlytek Animated Sketch | Render restricted HTML/SVG/CSS to GIF |

Search for `iFlytek` in the node selector. A first workflow can connect **Manual Trigger → iFlytek Translate**, select the credential, and enter text with source language `cn` and target language `en`. The result is in `data.translatedText`. Remote operations may incur charges.

## Inputs, results, and recovery

Text nodes accept direct text or UTF-8 binary; direct text takes precedence. File nodes read n8n binary properties instead of arbitrary host paths. Results are in `json.data`; generated audio, images, and reports are in n8n binary properties. Input item pairing is preserved. Temporary files are removed after n8n persists the output.

The default error behavior stops the node. **On Error → Continue (using regular output)** returns item errors in `json.error`. Task creation is separate from completion: persist task IDs and query them after a Wait node or an interrupted execution. Do not automatically retry paid submissions when their outcome is uncertain. Cancellation of a local process does not cancel a remote task.

Contract results require human review. Animated Sketch renders existing restricted HTML; it does not generate diagrams from natural language or execute arbitrary JavaScript. Voice training uses HTTPS with certificate verification and no redirects. Training task IDs remain opaque strings; binary sample upload also submits training, whereas URL upload requires a separate submission.

## Workflows and documentation

The `workflows/` directory contains three optional examples for text-processing chains, binary file input, and binary audio output: proofreading with explicit translation approval, invoice extraction for review, and text-to-MP3 synthesis. Import a JSON file manually to use an example. Each workflow is inactive and has no credential bindings or saved execution data. Select your own credentials before running remote operations.

- [Importable workflow guide](docs/workflows.md) and [complete node reference](README.md) (Chinese).
- [Installation](docs/installation.md), [compatibility](docs/compatibility.md), and [operations/recovery](docs/operations.md) (Chinese).
- [Package changelog](CHANGELOG.md).
- [Report an issue](https://github.com/iflytek/iFly-Skills/issues/new?template=n8n-node.yml) with versions, deployment mode, node/operation, error code, and a sanitized reproduction. Never post credentials, signed URLs, or private documents.

The `n8n-community-node-package` keyword enables npm community-package indexing; search indexing can lag behind publication. Exact-name installation, node loading, and compatibility must be checked separately. The keyword does not grant n8n verified status or guarantee inclusion in the editor's verified-node directory.

## License

The package is [Apache-2.0](LICENSE). The diagram adaptation retains its [MIT notice](runtime/bridge/diagram/licenses/animated-sketch-diagram-MIT.txt); the bundled Kalam font is covered by [SIL OFL 1.1](runtime/bridge/diagram/licenses/Kalam-OFL.txt). Browser, ffmpeg, n8n, and other runtime components retain their respective licenses.
