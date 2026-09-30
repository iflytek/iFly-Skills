# Changelog

## n8n release controls

### Changed

- Removed the npm token reference from the publish job and documented OIDC trusted publishing, first-publish setup, and required environment reviewers.
- Raised the node package's production dependency audit threshold to high while retaining the independent test host's critical threshold.
- Extracted the current package version's changelog section into release notes, rejected missing, duplicate, or empty sections, and used those notes for GitHub releases.

## Scoped n8n package

### Changed

- Set the npm package name to `@iflytekopensource/n8n-nodes-iflytek`, synchronized lockfile metadata, declared CommonJS output, and condensed capability keywords and the package description.
- Updated installation paths, workflow node type identifiers, acceptance scripts, and release checks for the scoped package, including npm archive filenames and registry URLs.
- Reorganized the Chinese README around installation and the 11 nodes, moved detailed operation guidance into the shipped node reference, and updated English usage and package migration instructions.
- Distinguished the package's Node.js 24.x support policy from n8n version requirements, streamlined both READMEs, and moved detailed input/output and error behavior into the operations guide.
- Linked license notices and the diagram template to tracked source files while documenting their installed paths, and clarified credential field descriptions for n8n users.
- Documented organization publishing permissions and added checks for scoped package artifacts and workflow registration.

### Fixed

- Streamed release archives to tar for listing and extraction to avoid GNU tar interpreting Windows drive letters as remote hosts, with regression coverage for absolute output paths containing spaces.

## n8n package distribution and maintenance

### Added

- Added inactive, unbound workflow exports for reviewed proofreading/translation, invoice recognition, and MP3 synthesis, with user instructions and offline expression checks in real n8n.
- Added clean-source tarball preparation, runtime/archive integrity validation, registry metadata and checksum verification, and release regression coverage.
- Added a version-tagged release workflow with compatibility checks, production dependency auditing, protected publishing, registry installation verification, and package verification reports for GitHub releases.
- Added an isolated, locked n8n test host for compatibility and registry installation checks.
- Added an English package README, package-level changelog, maintainer release instructions, an n8n issue form, and npm dependency update configuration.

### Fixed

- Reused the upstream transcription request-body signing implementation and verified that voice-training adaptation preserves the upstream module's endpoint constants.
- Upgraded the locked test host to n8n 2.40.7 and fixed vulnerable XML, multipart, and archive dependency paths with scoped overrides.
- Removed unused legacy dependency entries, including expr-eval, from the host lock and added installed-dependency and consumer regression checks.
- Applied production dependency auditing to pull requests and reused the hardened host lock for current-version compatibility checks and registry installation verification.

## n8n CI compatibility fixes

### Fixed

- Signed speed-transcription JSON and multipart request bodies in the package adapter without relying on the upstream digest-prefix convention or modifying Skill sources.
- Updated offline HTTP response doubles and verified transcription request digests and HMAC signatures against the actual transmitted bytes.
- Waited for complete n8n node-type metadata during acceptance checks, with bounded retries for startup file generation, concise failure diagnostics, and regression coverage for partial responses and failure cases.
- Added a browser-specific AppArmor user-namespace allowance on restricted Linux CI runners and a sandboxed Chromium startup check before rendering tests.

## Voice training compatibility and secure transport

### Changed

- Routed voice-training authentication, JSON requests, and binary uploads through certificate-verified HTTPS in the package adapter, without modifying the original Skill files.
- Accepted opaque string training task IDs for sample uploads, submission, and status queries, while preserving compatibility with existing safe integer IDs.
- Rejected training redirects and retained fail-closed behavior for certificate errors without an HTTP fallback.
- Updated voice-training documentation and regression coverage for task IDs, secure transport, unchanged upstream module state, and business-error handling.

## Linux rendering and n8n load validation

### Added

- Added a real n8n production-webhook load harness for local voice listing and optional GIF rendering at concurrency levels 1, 2, and 4, including execution persistence, CPU/RSS sampling, binary decoding, and cleanup checks.
- Added a Chromium seccomp profile and container setup guidance for sandboxed rendering with a non-root user and dropped container capabilities.

### Changed

- Enabled actual Linux browser and ffmpeg regression checks in the compatibility workflow.
- Updated Linux runtime compatibility and contributor instructions for the additional validation tools.
- Kept the n8n acceptance harness's Node.js compilation cache inside its disposable test directory.

## Execution controls and operational acceptance

### Added

- Added bounded administrator settings for per-process concurrency, pending requests, and execution deadlines.
- Added opt-in n8n execution metadata logging with request correlation, queue and total duration, controlled error codes, and binary byte counts.
- Added an installed-package preflight command for runtime integrity, registered modules, pinned Python dependencies, and local execution.
- Added invocation ownership markers and an offline recovery command that retains active, foreign, recent, or unrecognized directories.
- Added local load and real n8n acceptance harnesses, regression coverage, compatibility CI, and operational guidance for recovery, duplicate-charge prevention, and package rollback.

### Changed

- Validated public file and callback URLs in the package adapter, rejecting private DNS destinations, URL credentials, unsupported ports, and ambiguous syntax.
- Included n8n operational documentation and the business-ledger SQL example under the package's `docs/` directory, with updated documentation links and acceptance-script paths.
- Expanded the npm description and keywords to describe the supported iFLYTEK Skills capabilities.
- Reworked the shipped README and documentation for package users, including installation, credentials, compatibility, and troubleshooting; kept source build and test instructions in a repository-only contribution guide.
- Set the package version to `0.1.0`, synchronized the lockfile, and removed the private-package flag.
- Added npm author, homepage, issue tracker, and public registry metadata; made the CI tarball installation independent of the package version.

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
