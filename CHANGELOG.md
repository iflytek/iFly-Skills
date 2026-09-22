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
