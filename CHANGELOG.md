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

## Four-node MVP execution support

### Added

- Registered four n8n node classes for translation, text proofreading, invoice OCR, and Hyper TTS.
- Added shared node helpers for per-item execution, text and binary input mapping, runtime configuration validation, and `continueOnFail` handling.
- Added bridge adapters for translation, proofreading, invoice recognition, Hyper TTS synthesis, and local voice listing, including MP3 artifact metadata.
- Added node metadata, adapter, and package tests, plus clean build output handling.

### Scope

- The four nodes use the shared `iflyApi` credential definition. Other Skills remain unregistered and are outside this change.

## Foundational OCR, transcription, and image understanding nodes

### Added

- Registered n8n nodes for PDF/image OCR, speed transcription, and image understanding.
- Added bridge operations for image recognition, PDF task creation/status/result retrieval, audio transcription task creation/status/result retrieval, and image analysis.
- Added operation-specific credential requirements and binary input mappings for image, PDF, and audio workflows.
- Added adapter and node coverage for the new operations, including task results and cleanup behavior.

### Scope

- These nodes use the shared `iflyApi` credential definition and remain part of the development package; other Skills and production publication are outside this change.

## Video translation and voice cloning node integration

### Added

- Added n8n node classes for video translation task creation, listing, lookup, and transcript confirmation.
- Added n8n node classes for voice-clone training text retrieval, training lifecycle management, sample upload, and synthesis.
- Added bridge operation registrations with operation-specific credential requirements and supported audio artifact MIME types.
- Extended adapter, node metadata, and package registration coverage for the two Skills.

### Scope

- Video translation accepts public video URLs and voice cloning accepts binary or public audio inputs according to each operation; both use the shared `iflyApi` credential. Contract review and Animated Sketch Diagram remain outside the enabled node set.

## Contract review and local diagram rendering

### Added

- Registered `IflyContractReview` and `IflyAnimatedSketch`, bringing the package to 11 nodes and 25 operations.
- Added package-owned contract adapters using shared `IFLY_*` credentials, existing Skill processors and API clients, bounded PDF/DOCX extraction, and Markdown/JSON reports. Preserved the original contract CLI, configuration, and client interfaces.
- Added a credential-free package-owned renderer that adapts the original Skill's CSS frame capture and GIF assembly sequence using Playwright Core, administrator-installed Chromium, and ffmpeg.
- Bundled the required workflow modules, diagram template, Kalam font and license notices, and a full Python dependency lock.
- Added execution coverage for all 11 nodes and 25 operations, real Skill clients with offline transports, and opt-in real GIF decoding, cancellation, and n8n binary integration tests.

### Fixed

- Added package-level compatibility for contract report summary recursion and unavailable confidence values; the adapter identifies model inference and local rule checks separately.
- Corrected image OCR signing within the package adapter so the hostname excludes the request path.
- Fixed PDF binary path conversion, text/URL input precedence, operation validation, and temporary output paths in node results.
- Clarified that binary voice sample upload also submits training, added explicit confirmation, and rejected training and proofreading business errors.
- Added package-level compatibility for the transcription digest prefix and final chunk size, incomplete synthesis/image streams, and TLS-verified voice synthesis.
- Aligned the package's proofreading HTTP Host header with the signed endpoint.
- Mapped invoice CLI exits caused by HTTP or connection failures to the node's controlled upstream error.
- Ensured package renderer frame cleanup also runs when browser startup or shutdown fails.

### Scope

- Contract results require human review; live service permissions and review quality have not been validated.
- Diagram rendering accepts existing restricted HTML and does not implement prompt-based generation. The development package remains unpublished.
- Restored all files under `skills/` to the integration baseline. Compatibility code and license notices reside in the n8n package; original Skill files are bundled without rewriting their contents.
