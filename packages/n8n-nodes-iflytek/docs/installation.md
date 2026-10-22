# Installation and configuration

This guide is for self-hosted n8n administrators and workflow authors. Setup has three parts: the npm node package, the Python environment, and n8n credentials. Installing the npm package does not install Python, a browser, or ffmpeg.

## Requirements

- This package supports Node.js 24.x (`>=24.0.0 <25`). See [compatibility](compatibility.md) for tested n8n versions and their Node.js requirements. Python 3.10 or newer and a dedicated virtual environment are also required.
- The n8n execution process must be allowed to launch local Python processes and write to a dedicated temporary directory.
- Remote operations require iFLYTEK application credentials, access to the relevant services, and available quota. Diagram rendering does not require API credentials.
- In queue mode, install the same package and dependencies in every environment that executes workflows.

## Install the node package

For versions available in the registry, an instance administrator can install `@iflytekopensource/n8n-nodes-iflytek-skills` through **Settings → Community Nodes → Install**. The instance must allow unverified community nodes; availability depends on the registry and instance policy. The `n8n-community-node-package` keyword supports npm community package discovery. It does not grant n8n verified status or automatic inclusion in the editor's verified-node catalogue.

You can also follow n8n's [manual community-node installation guide](https://docs.n8n.io/integrations/community-nodes/installation/manual-install/). Run the following command in the community-node directory used by your instance, replacing `VERSION` with a published version:

```sh
npm install --save-exact "@iflytekopensource/n8n-nodes-iflytek-skills@VERSION"
```

The default directory is `.n8n/nodes` under the n8n service user's home directory. For custom user directories or container mounts, use the instance's actual configuration. To install a maintainer-provided `.tgz`, run `npm install --save-exact` in the same directory with the archive's absolute path. The global npm installation directory is not the community-node directory.

After installation, the following files should be under `node_modules/@iflytekopensource/n8n-nodes-iflytek-skills/`:

| Path | Purpose |
| --- | --- |
| `dist/` | n8n nodes, credentials, and administrator commands |
| `runtime/requirements/` | Python dependency locks |
| `runtime/bridge/diagram/workflow.html` | Diagram HTML template |
| `docs/` | Installation, compatibility, and operations guides |
| `workflows/` | Example workflow JSON files for manual import |

Instance administrators install and maintain the n8n host and its dependencies, including security updates.

In the examples below, the "package directory" means this installed directory. Normal use does not require a repository checkout, TypeScript compilation, or source tests.

## Migrating existing test workflows

Workflows created with earlier development packages contain the previous package name in their node types. Export workflows and back up n8n data before migrating. In the workflow JSON's `nodes[].type` fields, replace the applicable prefix below, keeping the node name suffix and other fields unchanged.

| Previous node type prefix | Current node type prefix |
| --- | --- |
| `n8n-nodes-iflytek.` | `@iflytekopensource/n8n-nodes-iflytek-skills.` |
| `@iflytekopensource/n8n-nodes-iflytek.` | `@iflytekopensource/n8n-nodes-iflytek-skills.` |

Pause affected workflows during a maintenance window. Uninstall the old package through n8n before installing this package to avoid duplicate node names and shared credential registration. Reimport workflows and check credential selections, expressions, and binary fields before resuming. The credential type remains `iflyApi`; existing credentials can be selected again if retained by the instance. npm treats different package names as separate packages, not an automatic upgrade path.

## Configure Python

Replace the example paths with paths on your host. Create the virtual environment as the n8n service user or grant that user access. The same user must be able to write to the temporary directory.

### Linux

```sh
ifly_package_root="/absolute/path/.n8n/nodes/node_modules/@iflytekopensource/n8n-nodes-iflytek-skills"
ifly_venv="/absolute/path/iflytek-venv"
ifly_tmp="/absolute/path/iflytek-tmp"

python3 -m venv "$ifly_venv"
"$ifly_venv/bin/python" -m pip install -r "$ifly_package_root/runtime/requirements/requirements-core.lock"
"$ifly_venv/bin/python" -m pip check
mkdir -p "$ifly_tmp"

export IFLYTEK_PYTHON_EXECUTABLE="$ifly_venv/bin/python"
export IFLYTEK_TMP_ROOT="$ifly_tmp"
node "$ifly_package_root/dist/shared/preflight.js"
```

### Windows PowerShell

```powershell
$iflyPackageRoot = 'C:\path\to\.n8n\nodes\node_modules\@iflytekopensource\n8n-nodes-iflytek-skills'
$iflyVenv = 'C:\path\to\iflytek-venv'
$iflyTmp = 'C:\path\to\iflytek-tmp'

python -m venv $iflyVenv
$iflyPython = Join-Path $iflyVenv 'Scripts\python.exe'
& $iflyPython -m pip install -r (Join-Path $iflyPackageRoot 'runtime\requirements\requirements-core.lock')
& $iflyPython -m pip check
New-Item -ItemType Directory -Path $iflyTmp -Force | Out-Null

$env:IFLYTEK_PYTHON_EXECUTABLE = $iflyPython
$env:IFLYTEK_TMP_ROOT = $iflyTmp
node (Join-Path $iflyPackageRoot 'dist\shared\preflight.js')
```

These environment variables apply only to the current terminal and processes started from it. Start n8n in that environment. For system services, containers, or process managers, add the variables to the service configuration and restart the processes that execute workflows. Container configurations must use paths accessible inside the container, not host paths.

A successful preflight confirms that package files, core dependencies, and local execution are available. It does not verify iFLYTEK service authorization. Preflight requires exact versions from the bundled dependency locks; a dedicated virtual environment prevents other applications from upgrading shared dependencies.

## Contract document and diagram dependencies

For contract PDFs, DOCX files, or document images, install `runtime/requirements/requirements-full.lock` in the same virtual environment. It includes the core dependencies. Replace `requirements-core.lock` with `requirements-full.lock` in the pip command above.

Diagram rendering also requires Chromium, Chrome, or Edge, plus ffmpeg, installed on the host. The npm dependency `playwright-core` does not download a browser. Configure absolute executable paths, for example:

```sh
# Linux example: use the paths from your installation.
export IFLYTEK_CHROME_EXECUTABLE="/usr/bin/chromium"
export IFLYTEK_FFMPEG_EXECUTABLE="/usr/bin/ffmpeg"
```

```powershell
# Windows example: use the paths from your installation.
$env:IFLYTEK_CHROME_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$env:IFLYTEK_FFMPEG_EXECUTABLE = 'C:\path\to\ffmpeg.exe'
```

On Linux, use a non-root environment that supports the Chromium sandbox. This package does not disable the browser sandbox. Install suitable host fonts to render Chinese text.

Once full Python dependencies and rendering programs are configured, run `node dist/shared/preflight.js --full` in the package directory. `--full` checks both contract dependencies and rendering programs; it is not a contract-only check. Then run **iFlytek Animated Sketch** using the installed `runtime/bridge/diagram/workflow.html` ([view template](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/workflow.html)) and confirm that `binary.image` is readable. Path checks do not replace an actual render.

## Rendering in Linux containers

Preinstall matching versions of the node package, Python dependencies, browser, ffmpeg, and fonts in the image, and run as a non-root user. Paths inside the image must match the `IFLYTEK_*_EXECUTABLE` settings. n8n data and temporary directories must be writable; the package and dependencies can be on a read-only filesystem.

With `--cap-drop=ALL` and `--security-opt=no-new-privileges`, the browser's user namespace sandbox still needs the relevant system calls. Copy the bundled [Chromium seccomp profile](chromium-seccomp.json) to the Docker host and add `--security-opt seccomp=/absolute/path/chromium-seccomp.json` to the container startup options. The profile is based on [Playwright v1.61.1's Docker policy](https://github.com/microsoft/playwright/blob/v1.61.1/utils/docker/seccomp_profile.json) (Apache-2.0). It retains the default deny policy and user namespace calls, adding `chroot` so Chromium can establish its sandbox inside its own namespace; kernel capability checks still apply.

Set memory, CPU, process, shared-memory, and temporary-disk limits for your workflows. See [compatibility](compatibility.md) for validated configurations. The kernel and host security policy must allow unprivileged user namespaces. If the sandbox fails to start, check deployment policy rather than using `--no-sandbox`, privileged containers, or disabling seccomp. A container used only for local rendering can have networking disabled; instances using remote iFLYTEK nodes still need outbound access to those services.

## Configure shared credentials

Create an **iFlytek API** credential in n8n using the **App ID**, **API Key**, and **API Secret** from the same iFLYTEK application, then select it in each node. Reusing credentials across capabilities does not automatically grant access to every service.

| Operations | Required fields |
| --- | --- |
| Translation, proofreading, invoice OCR, Hyper TTS synthesis, image OCR, speed transcription, image understanding, cloned speech synthesis, contract review | App ID, API Key, API Secret |
| PDF OCR task creation and queries | App ID, API Secret |
| Video translation | API Key, API Secret |
| Voice training | App ID, API Key |
| Hyper TTS `listVoices`, diagram rendering | None |

Contract review also needs Spark `generalv3.5` and access to the selected OCR, image understanding, and translation services. Voice, model, and cloned-resource permissions must match the application. The local voice list does not indicate account authorization.

Nodes use the credential selected in n8n. They do not fall back to host `IFLY_*`, `XFEI_*`, or `XFYUN_*` variables. After saving credentials, validate the target service with a small authorized sample.

## Post-installation checks

Restart n8n and search for `iFlytek` in the node selector. You can first run **iFlytek Hyper TTS → List Voices** to check local Python execution, then test the target capability with a small sample.

If nodes are missing, check the installation user, community-node directory, instance policy, and startup logs. If nodes appear but fail to execute, look up the error code in [troubleshooting](operations.md#troubleshooting). See [operations and recovery](operations.md) for concurrency, timeouts, logs, and queue deployment settings.
