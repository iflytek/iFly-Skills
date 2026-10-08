# Node reference

The package provides 11 nodes and 25 operations. See [installation](installation.md) for setup and shared credentials, and [operations](operations.md#inputs-results-and-errors) for input/output conventions.

## Operations and inputs/outputs

| Node | Operation | Input | Result |
| --- | --- | --- | --- |
| `iFlytek Translate` | `translate` | Text or UTF-8 binary, source and target languages | `data.sourceText`, `data.translatedText`, and language fields |
| `iFlytek Text Proofread` | `check` | Text or UTF-8 binary | Proofreading service result in `data.result` |
| `iFlytek Invoice OCR` | `recognize` | Invoice/receipt image or PDF binary | Structured recognition result in `data.result` |
| `iFlytek Hyper TTS` | `synthesize` | Text or UTF-8 binary, voice, and speech parameters | Synthesis information in `data` and MP3 in `binary.audio` |
| `iFlytek Hyper TTS` | `listVoices` | No business input | Bundled static voice constants; no service request |
| `iFlytek PDF and Image OCR` | `recognizeImage` | Image binary and result format | General image OCR result in `data.result` |
| `iFlytek PDF and Image OCR` | `createPdfTask` | PDF binary or public HTTP(S) URL, export format | `data.taskNo`, task status, and raw response |
| `iFlytek PDF and Image OCR` | `getPdfTask` | PDF OCR `taskNo` | Current status and raw response |
| `iFlytek PDF and Image OCR` | `getResult` | PDF OCR `taskNo` | Status, completion flag, and raw response |
| `iFlytek Speed Transcription` | `createTask` | MP3 binary, language, accent, and domain | `data.taskId` and upload URL |
| `iFlytek Speed Transcription` | `getTask` | Transcription `taskId` | Current status and raw response |
| `iFlytek Speed Transcription` | `getResult` | Transcription `taskId` | `data.text`, segments, status, and raw response |
| `iFlytek Image Understanding` | `analyze` | Image binary, question, and model parameters | `data.text` |
| `iFlytek Video Translate` | `createTask` | Public video HTTP(S) URL, source and target languages | Task information in `data.result` |
| `iFlytek Video Translate` | `listTasks` | No business input | Task list in `data.result` |
| `iFlytek Video Translate` | `getTask` | Video translation `taskId` | `data.taskId` and task details |
| `iFlytek Video Translate` | `confirmTranscript` | Video translation `taskId` and force-rerun option | Confirmation result in `data.result` |
| `iFlytek Voice Clone TTS` | `getTrainingText` | Training text set ID | Text segments in `data.result` |
| `iFlytek Voice Clone TTS` | `createTraining` | Task name, gender, engine, and language | Training task in `data.result` |
| `iFlytek Voice Clone TTS` | `uploadSample` | Training task ID, audio binary or URL, and text segment | `data.result` and `data.trainingSubmitted`; binary upload also submits training |
| `iFlytek Voice Clone TTS` | `submitTraining` | Training task ID | Submission result in `data.result` |
| `iFlytek Voice Clone TTS` | `getTraining` | Training task ID | Status, resource ID, and raw response |
| `iFlytek Voice Clone TTS` | `synthesize` | Text, cloned resource ID, and speech parameters | `binary.audio` and synthesis information |
| `iFlytek Contract Review` | `review` | Contract text or document binary, language, review mode, and focus | Structured review, Markdown in `binary.report`, and JSON in `binary.report2` |
| `iFlytek Animated Sketch` | `renderHtmlToGif` | Restricted HTML/SVG/CSS text or UTF-8 binary, dimensions, and animation parameters | GIF in `binary.image`, dimensions, and frame count |

Contract Review orchestrates multiple clients. Animated Sketch renders existing HTML and has no natural-language diagram generation operation. Invoice OCR and general PDF/image OCR are separate nodes and are not interchangeable.

## Usage

Remote file and callback URLs must use HTTP(S), ports 80/443, and resolve to public IPs. Private addresses, URL usernames/passwords, and fragments are rejected. The upstream service fetches content later and must control redirects and DNS changes. Use administrator-approved content domains in production.

### Text translation

Accepts text, source language, and target language, and returns the translation and language information. Set the languages with `fromLanguage` and `toLanguage`.

### Text proofreading

Accepts Chinese text and returns proofreading results in `data.result`. Service business-error codes are mapped to node errors.

### Invoice recognition

Accepts invoice/receipt images or PDF binary and returns recognition results in `data.result`.

### Hyper TTS speech synthesis

Accepts text, a voice, and speech parameters. Output defaults to `binary.audio` with the filename `speech.mp3`. Success requires the service's end frame. Results do not include temporary file paths that are subsequently cleaned up.

`listVoices` reads only the bundled static voice constants and does not call the synthesis service. Actual speech synthesis requires configured credentials and access to the relevant service.

### PDF and image OCR

Image recognition accepts image binary. PDF task creation accepts PDF binary or a public HTTP(S) URL; when a URL is provided, the binary field is ignored.

Both `getPdfTask` and `getResult` query PDF task status. A completion flag is returned for `FINISH` or `ANY_FAILED`. Download URLs come from the service response; the node does not automatically download result files.

### Speed transcription

Task creation accepts MP3 binary and optional language, accent, and domain settings. Use the returned `taskId` to query status or retrieve transcription text and segments.

### Image understanding

Accepts image binary and a question. Supports `general`/`imagev3`, `temperature` in `(0, 1]`, and `maxTokens` in `1..8192`. Text is returned only after the service's end frame arrives. Raw WebSocket frames are not exposed to n8n.

### Video translation

Creates tasks from public video HTTP(S) URLs; the node does not upload local video files. It can list tasks and retrieve details by `taskId`. `confirmTranscript` performs confirmation separately, with `forceRerun` explicitly controlling a subsequent rerun. Task submission is not automatically retried.

### Voice cloning

Training supports fetching text, creating tasks, uploading samples, submitting training, and querying status. A public sample URL takes precedence over binary input and only adds the audio; run `submitTraining` afterward. Binary upload also submits training: enable the node's confirmation option and keep input within 3 MiB. Then run `getTraining` rather than submitting again. `data.trainingSubmitted` indicates whether the operation submitted training. Audio duration, sample rate, and content must also satisfy service requirements. Training business-error codes are mapped to node errors.

The task ID from `createTraining` is at `data.result.data`. Reference it directly in subsequent operations' Task ID field, for example `={{ $json.data.result.data }}`. Preserve the full string instead of converting it to a number. Safe integer IDs in existing workflows remain compatible.

Synthesis requires a trained `resId` and supports MP3, PCM, Speex, and Opus output. Success requires the service's end frame.

Voice training uses HTTPS token/training endpoints with certificate validation, rejects redirects, and never falls back to HTTP. Cloned speech synthesis uses TLS WebSockets. Training counts, synthesis quota, and voice-resource permissions require separate authorization; see [service and platform limitations](compatibility.md).

### Contract review

Accepts direct text, UTF-8 binary, or explicitly selected PDF, DOCX, PNG, JPEG, or BMP binary. Documents are limited to 20 MiB; image OCR input is limited to 4 MiB. PDFs can contain up to 8 pages, rasterized page by page with a maximum long edge of 1600 pixels before image OCR. Extracted text is limited to 4000 characters. Exceeding the limit fails instead of silently truncating. Callers must split longer contracts and review relationships between segments separately. DOCX extraction reads body paragraphs and tables, excluding headers, footers, comments, text boxes, and embedded objects.

OCR is the default image extraction method. Explicitly choosing Image Understanding marks the result as model inference; OCR failures do not automatically switch services. Text goes through rule checks and Spark `v3.5/chat` review, with optional translation of the Chinese model summary into English. Compliance and bilingual checks use local rules. Model risk quotations are checked against the submitted text. All results require human review. Recognition confidence is not supplied unless provided by the service.

A required-service failure produces a controlled error without automatic retries. The shared total timeout applies to the whole call, including per-page OCR (120 seconds by default, configurable by an administrator). JSON results include rule and model output. Temporary Markdown/JSON report files are removed after persistence into n8n binary storage.

### Diagram rendering

Start with the installed `runtime/bridge/diagram/workflow.html` ([restricted flowchart template](https://github.com/iflytek/iFly-Skills/blob/main/packages/n8n-nodes-iflytek/python/diagram/workflow.html)) and pass the edited HTML text to the node. Common HTML text containers, basic SVG shapes, and CSS animation are supported. Scripts, event attributes, iframes, forms, external images, links, user-provided font resources, CSS URLs, escapes, and comments are rejected. The renderer disables page JavaScript, blocks external requests, and embeds the bundled Kalam font. Chinese text uses fonts installed on the host as fallbacks.

Input limits are 256 KiB and 2000 elements. Width is 64–1600, height 64–1200, frame rate 1–25, duration 100–5000 ms, and scale 1 or 2. The total pixel budget is `ceil(durationMs × fps / 1000) × width × height × scale² ≤ 120,000,000`. Match dimensions and duration to the HTML; arbitrary animations are not guaranteed to loop seamlessly. GIF output is limited to 32 MiB.

Format restrictions and resource blocking do not replace container/system isolation in production. Limit browser memory, CPU, and filesystem access according to your deployment requirements.
