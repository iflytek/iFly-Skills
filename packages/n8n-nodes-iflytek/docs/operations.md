# Node operations and recovery

This guide covers administration of installed iFlytek nodes. Complete [installation and configuration](installation.md), then configure capacity, logs, and recovery for every execution process. See [compatibility](compatibility.md) for version and platform requirements. Run the `node dist/shared/...` commands below from the installed `@iflytekopensource/n8n-nodes-iflytek-skills` package directory.

## Inputs, results, and errors

Pass files through n8n binary fields. For example, if an upstream file is at `binary.data`, set **Input Binary Field** to `data`; no local file path is needed. Nodes that accept text prefer **Text** and read the specified UTF-8 binary field only when Text is empty.

Each input item produces one output item and preserves n8n item linking. Business results are in `json.data`. Audio, images, and reports use `binary.audio`, `binary.image`, and `binary.report` / `binary.report2` by default. Pass these fields to nodes that upload, save, or send files. After n8n persists files, this package removes the invocation's temporary directory; workflows should pass files through binary fields.

JSON output also includes `ok`, `status`, `requestId`, and `meta.durationMs`. The outer `ok: true` and `status: succeeded` indicate a successful node call. For newly created remote tasks, check the service result in `data` to determine whether processing has completed. Save the returned task ID, then use Wait and query nodes to wait for completion; see [long-running tasks and recovery](#long-running-tasks-duplicate-charges-and-worker-recovery).

Errors stop the node by default. With **On Error → Continue (using regular output)**, item-level errors are returned in `json.error`; downstream nodes should check for this field first. Shared configuration errors, such as interpreter settings, can still stop the whole node. See [troubleshooting](#troubleshooting) for error handling. Do not enable **Retry On Fail** directly on paid submissions, as retries can create duplicate charges.

## Runtime settings and readiness checks

| Administrator environment variable | Default / range | Purpose |
| --- | --- | --- |
| `IFLYTEK_PYTHON_EXECUTABLE` | Required absolute path | Python in a dedicated virtual environment |
| `IFLYTEK_TMP_ROOT` | System temporary directory | Use a dedicated local directory for each worker in production |
| `IFLYTEK_MAX_CONCURRENT_PROCESSES` | 2; 1–16 | Shared execution slots within one Node.js process |
| `IFLYTEK_MAX_QUEUED_REQUESTS` | 32; 0–256 | Calls allowed to wait for a slot; 0 disables waiting |
| `IFLYTEK_TIMEOUT_MS` | 120000; 1000–600000 | Total per-call deadline, including queuing, execution, and result persistence |
| `IFLYTEK_LOG_EXECUTIONS` | `false`; `true` / `false` | Structured execution metadata through the n8n logger |
| `IFLYTEK_CHROME_EXECUTABLE` / `IFLYTEK_FFMPEG_EXECUTABLE` | Absolute paths required for diagram rendering and `--full` preflight | Browser and ffmpeg |

Settings come from the process environment, not workflow fields. Concurrency settings are fixed at the first call in each process; restart all execution processes after changes. A slot covers writing inputs, child-process execution, persisting artifacts, and temporary-file cleanup. n8n can read binary data before a slot is acquired, which also consumes memory. Limit n8n workflow concurrency and input sizes as well.

Run in the installed `@iflytekopensource/n8n-nodes-iflytek-skills` directory:

```sh
node dist/shared/preflight.js
# Add --full when full dependencies are configured.
node dist/shared/preflight.js --full
```

Preflight checks Node.js 24, Python >=3.10, exact dependency versions against the locks, runtime integrity, node registration, environment settings, and local voice listing. `--full` also checks full Python dependencies, browser/ffmpeg paths, and Playwright Core. Run a template to verify actual rendering. Preflight does not call paid APIs and cannot verify service authorization.

Deploy under a non-root account. Keep the package and virtual environment read-only, with write access limited to n8n data and dedicated temporary directories. Set CPU, memory, PID, and temporary-disk limits for the workflow size; keep clocks synchronized and TLS verification enabled. Containers also need Python and required system programs, with runtime variables using paths inside the container.

## Logs and capacity

When logging is enabled, `iflytek.execution` events named `started` / `finished` include requestId, executionId, nodeType, itemIndex, skill, operation, workerPid, active, queued, queueMs, and durationMs. Finished events additionally include status, controlled error codes, an exit code when available, and binary byte counts. Duration includes cleanup; queue duration is reported separately. Failures before reading input binary or credentials are still recorded as n8n node errors. Logging failures do not change business results.

Logs exclude content bodies, credentials, signed URLs, raw stderr, file paths, user-defined node names, and raw upstream responses. Do not use requestId/executionId as metric labels. Aggregate success rates and P95 latency by skill, operation, and status. Alert on `QUEUE_FULL`, timeouts, startup failures, cleanup failures, disk pressure, and persistent upstream errors. The controlled `UPSTREAM_ERROR` does not distinguish quota from authentication failures; check the service console.

n8n execution history and binary storage may still contain business data. Configure their access controls, success/failure execution persistence, and retention separately. Binary byte counts are resource statistics, not a substitute for iFLYTEK billing. Failed or cancelled calls and lost responses can still incur charges.

Total concurrency depends on all execution processes: 4 workers × 2 slots per process can occupy up to 8 slots. Manage account quota together with n8n execution concurrency and rate limits at the business entry point. This package does not provide a global quota service across instances.

## Temporary directories and abnormal exits

After success, failure, cancellation, or timeout, the package attempts to remove the call's `ifly-exec-*` directory. Cleanup failures report `CLEANUP_FAILED`. The directory's `.ifly-owner.json` records the host, Node.js PID, and creation time for recovery checks. If the operating system forcibly kills a worker, perform offline recovery during a maintenance window.

1. Stop the worker that owns the temporary directory and confirm that its Python, Node, browser, and ffmpeg descendants have stopped. The absence of the parent PID alone does not establish that child processes have exited.
2. Preview leftovers at least 24 hours old before applying deletion:

```sh
node dist/shared/tempRecovery.js --root /var/tmp/ifly-worker-a --min-age-hours 24
node dist/shared/tempRecovery.js --root /var/tmp/ifly-worker-a --min-age-hours 24 --apply --workers-stopped
```

The tool rejects filesystem roots, the system temporary directory itself, and symlink roots. It only handles directories with this package's naming pattern, a matching host, a stopped owner, and sufficient age. Active or unknown PIDs, other hosts, missing or invalid markers, recent directories, and unrelated content are retained. A PID reused by another process also causes retention for administrator review. Old directories without markers require separate review; ownership is not inferred automatically.

`--workers-stopped` is an administrator confirmation. The tool does not stop processes and is unsuitable for scheduled cleanup while workers are running. Shared temporary directories do not replace dedicated worker directories. Changes to container hostnames or PID namespaces can cause old markers to be conservatively retained.

## URLs, training, and rendering boundaries

PDF, video, voice-sample, and callback URLs must be public HTTP(S) addresses on ports 80/443, without usernames/passwords or fragments. The adapter rejects local, private, link-local, and reserved addresses, mixed DNS results, and DNS resolution failures. Resolution time is bounded by the runner's total deadline.

The upstream provider fetches these URLs later. This package does not download user content and cannot pin the provider's later DNS results or control redirects. In production, use administrator-approved content domains that do not redirect to internal networks, and enforce provider-side fetching and deployment egress controls. A single DNS check is not complete SSRF isolation.

Voice-training token requests use `https://avatar-hci.xfyousheng.com/aiauth/v1/token`; training and upload requests use `https://opentrain.xfyousheng.com/voice_train`. Requests verify TLS certificates and reject redirects. Connection or certificate errors fail directly. Cloned speech synthesis uses WebSockets with TLS verification.

Rendering accepts only restricted HTML/SVG/CSS, disables page scripts and external requests, and retains the Chromium sandbox. Deployment administrators remain responsible for container isolation, system resource limits, and browser patches. The package does not expose arbitrary script execution or natural-language diagram generation.

## Long-running tasks, duplicate charges, and worker recovery

After Create/Submit succeeds, durably save the business correlation key, input digest, and upstream task ID before entering n8n Wait. Get queries once; workflows must set their own polling limit and deadline. During recovery, query the saved task ID instead of calling Create again. Ending the local wait or process does not cancel an upstream task.

Do not enable n8n Retry On Fail for paid operations. Queue redelivery after failures and application re-execution can also duplicate submissions. This package's requestId, in-process queue, and temporary directories do not provide business-level idempotency.

For cross-worker deduplication, you can use the [operation ledger example](operation-ledger.sql) in a separate business PostgreSQL database, with queries executed by your workflow's Postgres nodes or application service. iFlytek nodes do not automatically create, read, or write this table. Do not install it in n8n's internal database.

Before submission, atomically reserve a record with the unique key `scope + skill + operation + operation_key`. Only the caller that successfully inserts the record submits upstream. `scope` distinguishes the business or application; `operation_key` is a business key that stays the same across retries. Compute `request_sha256` from canonical input, including parameters that affect results and file-content digests, without storing bodies or secrets. For duplicate keys, compare digests: read the existing state for identical input and reject different input. Do not place the paid request inside a database transaction that can retry automatically.

Suggested states are `pending_submission → submitted → succeeded/failed`. If a response is lost, a process exits, or a credential/network error cannot prove that submission did not occur, record `submission_unknown` and reconcile manually. Do not expire the reservation by TTL or submit another paid request. Record submitted only after obtaining a task ID; expired pending records require reconciliation. Atomic reservation prevents ordinary concurrent duplicate submissions but cannot guarantee exactly-once behavior between an external API and a database.

In queue mode, use binary storage supported by the target n8n version and accessible to all workers. Do not use one worker's filesystem binary storage or this package's temporary directories for cross-worker data. Check object-storage capabilities and licensing separately for large files. The main process and workers must share the credential encryption key, database, and Redis configuration.

## Upgrades and rollback

1. Record the current package version and retain an installable artifact, matching Python dependencies, and runtime image. Verify origin and integrity under your organization's requirements. Back up n8n data, the credential encryption key, and business submission records.
2. Pause new paid submissions, wait for active calls to finish, and save remote task IDs. Reconcile uncertain submissions.
3. Install the target version in an isolated instance, run preflight, and check existing workflows, multiple items/expressions, binary data, error branches, and Wait recovery. Then switch all workers to the same version together.
4. To roll back, restore the previous npm artifact and matching Python/system dependencies. Do not resubmit completed or uncertain upstream tasks. Check node-version and output-field compatibility before resuming Wait executions.
5. Handle node-package rollback separately from n8n database migration rollback. Before upgrading n8n, verify database backup/restore according to n8n's instructions. Replacing the node package is not a database rollback.

Stop affected execution processes before upgrades or rollback so a workflow does not execute against mixed versions. Restoring the node package does not restore or cancel upstream tasks. Continue querying with saved task IDs.

## Troubleshooting

Check the package, n8n, Node.js, and Python versions and the node operation first. Run `node dist/shared/preflight.js` in the package directory to rule out interpreter, dependency, file-integrity, and basic configuration problems.

| Symptom or error code | Checks and actions |
| --- | --- |
| iFlytek nodes are missing | Confirm installation in the instance's community-node directory, permission to load community nodes, and a restart after installation; check startup logs |
| `INVALID_INPUT` | Check text, binary field names, file formats/sizes, URLs, and node parameters; also verify administrator settings are within their allowed ranges |
| `AUTH_FAILED` | Select an iFlytek API credential with all required fields; do not substitute host environment variables for n8n credentials |
| `PYTHON_NOT_FOUND` / `DEPENDENCY_MISSING` | Check absolute paths, service-account permissions, and locked virtual-environment dependencies; rendering also needs a browser and ffmpeg |
| `RUNTIME_MISSING` / `INVALID_PROTOCOL` | Check package integrity and reinstall a known version; if persistent, provide a sanitized requestId and version details |
| `UPSTREAM_ERROR` | Check service, model, voice, resource access, and quota in the iFLYTEK console, plus clocks and networking; the error does not distinguish every upstream authentication/quota cause |
| `QUEUE_FULL` | Check workflow concurrency, execution backlog, and account limits; administrators can adjust slots or queue capacity if resources permit |
| `PROCESS_TIMEOUT` / `EXECUTION_CANCELLED` | Local waiting has ended, but asynchronous tasks may still run remotely. Query a saved task ID or reconcile manually before deciding what to do next |
| `BINARY_IO` / `INVALID_ARTIFACT` / `OUTPUT_LIMIT_EXCEEDED` | Check binary field names, artifact sizes, storage permissions, and disk capacity; in queue mode, check shared binary storage |
| `CLEANUP_FAILED` / `PROCESS_TERMINATION_FAILED` | Check active calls and descendant processes; handle leftovers during a maintenance window, without cleaning active tasks |

Diagnostic logs provide controlled error information only. When reporting a [project issue](https://github.com/iflytek/iFly-Skills/issues), include a minimal reproduction and requestId when available. Do not disclose credentials, signed URLs, or business content.
