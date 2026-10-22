# Example workflows

The package includes three importable n8n examples demonstrating text processing, binary file input, and binary audio output. Choose an example for the input/output pattern you need, then use the [node reference](nodes.md) to combine other capabilities.

Examples are for manual import and customization. Installing or running the nodes does not depend on importing them.

## Import and configure

After installing the package and configuring Python, choose **Import from File** in the n8n editor and select a JSON file from the installed package's `workflows/` directory. You can also download the files from the repository. All templates use manual triggers, are inactive, and contain no credential bindings, pinned execution data, or real business files.

| Example | Purpose | Configuration before use |
| --- | --- | --- |
| [Proofread and translate](../workflows/proofread-and-translate.json) | Review Chinese proofreading results, then translate selected text after explicit confirmation | Select iFlytek API credentials for Proofread and Translate; edit Text input |
| [Invoice recognition](../workflows/invoice-recognition.json) | Read an image or PDF and return service fields for human review | Replace the Read invoice path or binary source; select OCR credentials |
| [Text to speech](../workflows/text-to-speech.json) | Synthesize text into a downloadable MP3 | Select synthesis credentials and an authorized voice; edit the text |

In the proofreading template, `approvedForTranslation` starts as `false`, so the first run only proofreads and returns suggestions. After review, put the selected text in `approvedText`, set `approvedForTranslation` to `true`, and run again. The second run calls proofreading again and also calls translation. The template does not automatically accept suggestions or wait for an external approval system.

The invoice template uses `/files/invoice.jpg` as a placeholder. The file must be readable on the host or worker that executes the node and comply with n8n's file-access policy. In a container, you can mount your file directory read-only at `/files`. Alternatively, replace the read node with a source that supplies `binary.data`. Results preserve the service's original structure; review amounts, dates, tax IDs, and other fields before storing them.

The speech template's `synthesize` operation calls the iFLYTEK service and requires access and quota. The result is in `binary.audio` and can be downloaded from the execution output. `listVoices` is a static listing operation, distinct from the synthesis operation used here.

All three templates can incur service charges. Automatic retries are disabled on remote nodes. Validate with small, non-sensitive inputs first. Workflow authors can explicitly add storage, notification, or public-trigger nodes and the permissions those nodes require.
