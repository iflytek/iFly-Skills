# Changelog

## PR #91 — n8n integration scaffold

### Added

- Added the `n8n-nodes-iflytek` package skeleton for self-hosted n8n deployments.
- Added the shared `IflyApi` credential definition with `appId`, `apiKey`, and `apiSecret` fields mapped to the unified `IFLY_*` environment names.
- Added the Skill catalog and allow-listed runtime staging process for the nine directly executable Skills and their ten Python runtime files.
- Added the locked core Python dependency list and package-level checks for catalog completeness, credential metadata, runtime staging, source integrity, and stale-output protection.

### Changed

- Normalized the supported Skill credential documentation and runtime scripts to use `IFLY_*`, while retaining the documented legacy-prefix compatibility in the Skill implementations.
- Updated the repository and package documentation to describe the n8n package boundary, deferred capabilities, build inputs, and current non-published status.

This entry describes the scaffold and credential/catalog preparation delivered by PR #91. Executable n8n business nodes and the shared Python execution layer are not included in this entry.

## Shared Python execution layer

### Added

- Added the shared `PythonRunner` and process-control utilities for bounded `child_process.spawn` execution.
- Added the JSON bridge and operation manifest used to validate requests, isolate allow-listed credentials, and return structured results.
- Added binary input/output lifecycle handling, artifact validation, timeout and cancellation propagation, deterministic error mapping, and cleanup.
- Added execution-layer tests covering protocol validation, process failures, cancellation, timeouts, binary limits, and package execution.

### Scope

- The bridge currently enables only the local `iflytek-hyper-tts/listVoices` operation. Business nodes and remote Skill API adapters are outside this change.
