# Compatibility and limitations

When selecting a deployment environment, check n8n, Node.js, Python, system programs, and iFLYTEK service permissions together. This page describes the package's supported conditions; setup instructions are in [installation and configuration](installation.md).

## Runtime environment

| Component | Requirement or validated version | Notes |
| --- | --- | --- |
| n8n | Validated: 2.39.8, 2.40.5, 2.40.7 | Covers node registration, manual/production execution, multiple items, expressions, and continuing on errors; this does not mean every remote operation has been tested with service authorization |
| Node.js support for this package | 24.x; validated: 24.18.0 | `engines.node` is `>=24.0.0 <25`; preflight also requires major version 24 |
| Python | Minimum: 3.10; validated: 3.10.12, 3.13.14 | Use a dedicated virtual environment and the bundled dependency locks |
| Windows | x64, Python 3.13.14 | Local execution and Edge/ffmpeg rendering validated |
| Linux | Ubuntu 22.04 / WSL2, x64, Python 3.10.12 | Local execution, queue recovery, and Chrome Headless Shell 149.0.7827.55 / ffmpeg 4.4.2 rendering, cancellation, and binary cleanup validated |
| Linux containers | Docker 29.1.3, Ubuntu 22.04, x64; host execution validated up to n8n 2.40.7 | Locked host, node loading, and Webhook execution validated; sandboxed rendering validated in a 2.40.5 container. Uses a non-root user, read-only root filesystem, dropped capabilities, and [Chromium seccomp](installation.md#rendering-in-linux-containers) |
| Diagrams | Chromium, Chrome, or Edge, plus ffmpeg | Administrators install these programs and configure absolute paths; Linux must support the browser sandbox |

n8n's own Node.js requirements vary by version. The npm metadata for [2.39.8](https://registry.npmjs.org/n8n/2.39.8), [2.40.5](https://registry.npmjs.org/n8n/2.40.5), and [2.40.7](https://registry.npmjs.org/n8n/2.40.7) declares `engines.node: >=24.0.0`. This does not imply that every n8n version requires Node.js 24.

This package limits support to the validated 24.x line and enforces that limit in `package.json` and preflight. It is a support requirement, not just a test-environment description. Node.js 25 and later are not currently supported by this package. Your installation must satisfy both n8n's requirements and this package's requirements.

Container validation used 2 CPUs, 2 GiB of memory, 512 PIDs/threads, and a 512 MiB temporary-filesystem limit to check the local operations above under resource constraints. Determine production capacity from your own files, concurrency, and workflows. These results do not establish compatibility with every base image, host kernel, or multi-host deployment.

`n8n-workflow >=2.39.3 <3` is the npm SDK peer range, not the n8n product version range. Other n8n/Python versions, macOS, ARM64, and other Linux distributions do not have equivalent validation results. Test your workflows in an isolated instance before adopting them.

The package starts local Python child processes and is intended for self-hosted instances where administrators can install system dependencies. n8n Cloud and managed environments that prohibit child processes or system dependency installation are outside its supported scope. A successful npm installation does not confirm a complete execution environment; run the bundled preflight.

## Dependencies by capability

| Usage | Python dependencies | Other requirements |
| --- | --- | --- |
| Remote speech, OCR, translation, proofreading, image understanding, and related operations | `runtime/requirements/requirements-core.lock` | Application access to the service and available quota |
| Contract PDF, DOCX, or document-image processing | `runtime/requirements/requirements-full.lock` (includes core) | Spark and selected OCR, translation, and image understanding service access |
| HTML diagram rendering | The core environment can be reused | Browser, ffmpeg, and suitable fonts; npm installs Playwright Core |

After package integrity and Python dependency checks pass, validate the target capability with your own inputs and application permissions. Preflight's static voice listing does not contact the speech synthesis service and cannot verify voice authorization or balance.

## Queues and file storage

In queue mode, every execution process needs the same node package, Python dependencies, and system programs. The Python interpreter and temporary directory must be accessible inside each worker.

Cross-worker Wait recovery and `database` binary reads/writes were validated with n8n 2.40.5, PostgreSQL 14.24, and Redis 6.0.16. This result applies to local processes; containers, multi-host networking, S3, and other binary backends need checks in the target environment.

Use binary storage supported by your n8n version and accessible to all workers. Do not use a worker's local filesystem binary storage or this package's temporary directories as cross-worker storage. Refer to the [n8n queue-mode documentation](https://docs.n8n.io/hosting/scaling/queue-mode/) for object-storage licensing and configuration.

Package concurrency limits apply separately to each Node.js process, not globally to an account. CPU, memory, and storage requirements depend on file sizes, audio/video duration, contract page counts, and rendering dimensions. Determine capacity using small samples and controlled loads from your workflows.

## Service and data boundaries

- **Service access:** shared credentials identify the same application; verify authorization and quotas separately for voices, models, cloned resources, and each API. Evaluate model and recognition quality with business-relevant samples.
- **Voice training:** token and training endpoints use HTTPS with certificate validation, reject redirects, and never fall back to HTTP. Cloned speech synthesis uses TLS WebSockets. Training samples must be authorized for use and satisfy service requirements. Check training access, training counts, and synthesis quota separately.
- **Video translation:** task creation requires available video-duration quota. A successful `listTasks` call does not establish that you can create tasks. If the service reports insufficient quota, check the application's relevant quota before submitting again.
- **Contract review:** rules and model analysis provide assistance and require human review. See [contract review](nodes.md#contract-review) for document formats, length limits, and page limits.
- **Diagrams:** only restricted HTML/SVG/CSS can be rendered to GIF. Arbitrary scripts and natural-language diagram generation are not supported. HTML that needs external images, remote fonts, or complex page scripts is unsuitable.
- **Remote URLs:** only HTTP(S) URLs on ports 80/443 that resolve to public IPs are accepted. The provider fetches content later; this package cannot control subsequent DNS resolution or redirects. Use trusted content domains.
- **Enterprise networks:** Python child processes do not inherit proxy environment variables, `PYTHONPATH`, or `NODE_OPTIONS` from the parent. If your network requires a proxy or custom certificates, verify service access from the execution environment; the n8n parent process's proxy configuration alone is insufficient.
- **Long-running tasks and charges:** local timeout or cancellation does not cancel a remote task. Save the task ID after creation and query it first during recovery. If submission status is uncertain, reconcile it manually to avoid duplicate charges.

## Before upgrading

Install the target version and its dependencies in an isolated instance, run preflight, and validate parameters, outputs, binary data, and error branches with your workflows. In queue mode, also validate Wait recovery. Then upgrade all workers together.

Rolling back the node package and rolling back n8n database migrations are separate operations. Keep a working package version and its dependencies, and back up workflows, the credential encryption key, and business submission records before upgrading. See [upgrades and rollback](operations.md#upgrades-and-rollback).
