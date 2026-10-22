# @iflytekopensource/iFLYTEK Skills

**npm package:** `@iflytekopensource/n8n-nodes-iflytek-skills`

iFLYTEK Skills for self-hosted n8n workflows, covering speech, images and documents, and multilingual processing. Remote services share an **iFlytek API** credential; Skills execute through local Python processes.

## Supported nodes

The package provides 11 nodes and 25 operations. See the [node reference](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/nodes.md) for operation details.

| Node | Capabilities |
| --- | --- |
| iFlytek Translate | Translate text |
| iFlytek Text Proofread | Proofread Chinese text |
| iFlytek Invoice OCR | Recognize invoice images or PDFs |
| iFlytek Hyper TTS | Synthesize speech; list bundled voices |
| iFlytek PDF and Image OCR | Recognize images; create and query PDF tasks |
| iFlytek Speed Transcription | Create and query MP3 transcription tasks |
| iFlytek Image Understanding | Answer questions about an image |
| iFlytek Video Translate | Create, query, and manage video translation tasks |
| iFlytek Voice Clone TTS | Train voices and synthesize cloned speech |
| iFlytek Contract Review | Review text or document contracts and return reports |
| iFlytek Animated Sketch | Render restricted HTML/SVG/CSS to GIF |

## Requirements

- **This package currently supports Node.js 24.x** (`>=24.0.0 <25`). Tested n8n versions and their Node.js requirements are listed in the [compatibility guide](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/compatibility.md).
- **Python 3.10 or newer**, with the bundled locked dependencies in a dedicated virtual environment. Contract document processing uses the full dependency profile.
- **Self-hosted n8n** with permission to launch local child processes and write temporary files. Diagram rendering also requires a browser and ffmpeg; see the [installation guide](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/installation.md).
- **iFLYTEK service access** for remote operations: an application with App ID, API Key, API Secret, and authorization and quota for each service you use.

## Installation

### 1. Install the community node package

Enter `@iflytekopensource/n8n-nodes-iflytek-skills` in **Settings → Community Nodes → Install**, or run this command in your instance's community-node directory (normally `~/.n8n/nodes`):

```sh
npm install --save-exact @iflytekopensource/n8n-nodes-iflytek-skills@VERSION
```

Replace `VERSION` with a published version. The instance must allow unverified community nodes. npm installation does not configure Python. Existing workflows using earlier development package names need the [migration procedure](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/installation.md).

### 2. Prepare the Python environment

Run the following from the **installed package directory**, normally `~/.n8n/nodes/node_modules/@iflytekopensource/n8n-nodes-iflytek-skills` on Linux or `C:\Users\<service-user>\.n8n\nodes\node_modules\@iflytekopensource\n8n-nodes-iflytek-skills` on Windows. Use the actual directory for custom n8n installations. Replace the example paths with locations accessible to the n8n service user. Use a dedicated virtual environment; no repository checkout or source build is needed.

**Linux**

```sh
python3 -m venv "/absolute/path/iflytek-venv"
"/absolute/path/iflytek-venv/bin/python" -m pip install -r runtime/requirements/requirements-core.lock
"/absolute/path/iflytek-venv/bin/python" -m pip check
export IFLYTEK_PYTHON_EXECUTABLE="/absolute/path/iflytek-venv/bin/python"
export IFLYTEK_TMP_ROOT="/absolute/path/iflytek-tmp"
mkdir -p "$IFLYTEK_TMP_ROOT"
node dist/shared/preflight.js
```

**Windows PowerShell**

```powershell
python -m venv 'C:\path\to\iflytek-venv'
& 'C:\path\to\iflytek-venv\Scripts\python.exe' -m pip install -r runtime/requirements/requirements-core.lock
& 'C:\path\to\iflytek-venv\Scripts\python.exe' -m pip check
$env:IFLYTEK_PYTHON_EXECUTABLE = 'C:\path\to\iflytek-venv\Scripts\python.exe'
$env:IFLYTEK_TMP_ROOT = 'C:\path\to\iflytek-tmp'
New-Item -ItemType Directory -Path $env:IFLYTEK_TMP_ROOT -Force | Out-Null
node dist/shared/preflight.js
```

For contract document processing, install `requirements-full.lock` instead of `requirements-core.lock`. Diagram rendering also needs a browser and ffmpeg; follow the [additional dependency setup](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/installation.md).

### 3. Apply settings and restart n8n

The examples set variables only in the current terminal. Configure the same variables in the service, container, or process manager that starts n8n, then restart the execution processes. In queue mode, configure every worker; paths must be accessible inside that worker or container.

Preflight checks local files and dependencies without calling a paid API. After restarting, search for `iFlytek` in the node selector. **iFlytek Hyper TTS → List Voices** can check local execution without API credentials; actual speech synthesis needs service authorization. Continue with the translation example below to test a remote service. See [troubleshooting](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/operations.md) if setup fails.

## Minimal example

1. Create an **iFlytek API** credential using the **App ID**, **API Key**, and **API Secret** from one application in the [iFLYTEK console](https://console.xfyun.cn/) with translation access and available quota.
2. Search for `iFlytek` in the node selector, connect **Manual Trigger → iFlytek Translate**, and select the credential.
3. Set **Text** to `欢迎使用 iFLYTEK Skills`, **Source Language** to `cn`, and **Target Language** to `en`, then execute the node.

Read the translation from `data.translatedText`, or use `{{ $json.data.translatedText }}` downstream. This example calls a paid translation service. Other node results are in `json.data`; files use n8n binary properties. See [input, result, and error behavior](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/operations.md) for details.

## Documentation and support

- [Installation](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/installation.md) and [compatibility](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/compatibility.md).
- [Node reference](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/nodes.md) and [importable example workflows](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/workflows.md).
- [Operations, errors, and recovery](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/operations.md), and the [package changelog](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/CHANGELOG.md).
- [Report an issue](https://github.com/iflytek/iFly-Skills/issues/new?template=n8n-node.yml) with versions, node/operation, error code, and a sanitized reproduction. Never post credentials or private documents.
- [Contributor guide](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/CONTRIBUTING.md) (Chinese).

## Limitations

- Local Python execution requires a self-hosted instance; n8n Cloud is not supported. The `n8n-community-node-package` keyword enables npm indexing, not n8n verified status or verified-node catalogue inclusion.
- Shared credentials still need authorization and quota for each remote service. Local diagram rendering and bundled voice listing do not call an API; speech synthesis requires service access.
- Remote operations send the supplied text, files, or URLs to iFLYTEK services. Local Python execution does not make those operations offline.
- Contract results require human review. Animated Sketch renders existing HTML, not natural-language diagram requests. See the [operations guide](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/docs/operations.md) before retrying or recovering paid tasks.

## License

The package is [Apache-2.0](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/LICENSE). The diagram adaptation retains its [MIT notice](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/licenses/animated-sketch-diagram-MIT.txt); the bundled Kalam font is covered by [SIL OFL 1.1](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/licenses/Kalam-OFL.txt). Both notices are included in `runtime/bridge/diagram/licenses/`. Browsers, ffmpeg, and other dependencies retain their respective licenses.
