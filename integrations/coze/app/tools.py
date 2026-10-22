"""Attach the 24 concrete tools to the fixed catalog, with typed HTTP contracts."""

from typing import Annotated

from fastapi import Request, Query

from . import models as m
from .catalog import Tool
from .routing import register_tool


# Explicit per-operation contracts; no caller-selected module, command or kwargs.
CONTRACTS = {
    "iflytek-translate": {"translate": (m.Translate, m.Translation)},
    "iflytek-text-proofread": {"check": (m.Proofread, m.Proofreading)},
    "iflytek-ocr-invoice": {"recognize": (m.ImageInput, m.Recognition)},
    "iflytek-hyper-tts": {"synthesize": (m.HyperSpeech, m.Audio), "list_voices": (None, m.Voices)},
    "iflytek-pdf-image-ocr": {"recognize_image": (m.ImageOCR, m.OCRResult), "create_pdf_task": (m.PDFSubmission, m.Job[m.PDFResult]), "get_pdf_task": (None, m.Job[m.PDFResult])},
    "iflytek-speed-transcription": {"create_task": (m.TranscriptionSubmission, m.Job[m.TranscriptionResult]), "get_task": (None, m.Job[m.TranscriptionResult])},
    "iflytek-image-understanding": {"analyze": (m.Analyze, m.Analysis)},
    "iflytek-video-translate": {"create_task": (m.VideoSubmission, m.Job[m.VideoResult]), "get_task": (None, m.Job[m.VideoResult]), "confirm_transcript": (m.TaskAction, m.Job[m.VideoResult])},
    "iflytek-voiceclone-tts": {"get_training_text": (None, m.TrainingText), "create_training": (m.TrainingSubmission, m.Job[m.TrainingResult]), "upload_sample": (m.UploadSample, m.Job[m.TrainingResult]), "submit_training": (m.TaskAction, m.Job[m.TrainingResult]), "get_training": (None, m.Job[m.TrainingResult]), "synthesize": (m.CloneSpeech, m.Audio)},
    "iflytek-contract-intelligence-review": {"review": (m.Review, m.Job[m.ReviewResult]), "get_review": (None, m.Job[m.ReviewResult])},
    "animated-sketch-diagram": {"render_html_to_gif": (m.Render, m.Job[m.RenderResult]), "get_render": (None, m.Job[m.RenderResult])},
}


DESCRIPTIONS = {
    "iflytek-translate": {"translate": ("Translate text", "Translate up to 4096 UTF-8 bytes between the selected languages.")},
    "iflytek-text-proofread": {"check": ("Proofread Chinese text", "Return spelling and wording suggestions with provider offsets; does not modify the input.")},
    "iflytek-ocr-invoice": {"recognize": ("Recognize an invoice image", "Read structured invoice fields from a public HTTPS PNG or JPEG, up to 4 MiB.")},
    "iflytek-hyper-tts": {
        "synthesize": ("Synthesize speech", "Return a complete MP3 and its expiring HTTPS URL. The deployment account must have permission for the selected voice."),
        "list_voices": ("List speech voices", "Return the built-in voice catalog. Listing a voice does not establish the account's synthesis permission."),
    },
    "iflytek-pdf-image-ocr": {
        "recognize_image": ("Recognize text in an image", "Read a PNG or JPEG up to 4 MiB and return JSON, Markdown, or both."),
        "create_pdf_task": ("Submit a PDF for recognition", "Accept a public HTTPS PDF up to 32 MiB and 100 pages. Query get_pdf_task for completion and output files."),
        "get_pdf_task": ("Query PDF recognition", "Return recognition status, page details and expiring output URLs. partially_succeeded retains page failures."),
    },
    "iflytek-speed-transcription": {
        "create_task": ("Submit audio for transcription", "Accept a public HTTPS MP3 up to 128 MiB. The fixed language settings automatically recognize Chinese and English; query get_task for the transcript."),
        "get_task": ("Query audio transcription", "Return task state and the completed transcript with provider timestamps."),
    },
    "iflytek-image-understanding": {"analyze": ("Analyze an image", "Answer a question about a public HTTPS PNG or JPEG up to 4 MiB; return the complete response.")},
    "iflytek-video-translate": {
        "create_task": ("Submit a video for translation", "Accept a public HTTPS MP4 up to 128 MiB. Query get_task and inspect any waiting_input stage before confirming."),
        "get_task": ("Query video translation", "Return the current stage for this workspace's task. Output details and artifacts are returned only after success; waiting_input does not include transcript contents."),
        "confirm_transcript": ("Confirm video transcript", "Accept the provider transcript unchanged when the task is waiting_input; this tool does not preview or edit subtitles."),
    },
    "iflytek-voiceclone-tts": {
        "get_training_text": ("Get voice training text", "Choose a returned text segment and record its exact contents. Arbitrary transcripts cannot replace the provider text."),
        "create_training": ("Create a voice training task", "Create a task for an authorized speaker. Next upload_sample, then explicitly submit_training."),
        "upload_sample": ("Upload a voice training sample", "Register, without submitting, a public HTTPS mono WAV (16 bit) or MP3: at least 24 kHz, at most 40 seconds and 3 MiB. Recording content must match text_id and seg_id."),
        "submit_training": ("Submit voice training", "Submit only after sample_uploaded; query get_training until trained or failed."),
        "get_training": ("Query voice training", "Return the training stage, a safe failure reason when known, and res_id after successful training."),
        "synthesize": ("Synthesize with a cloned voice", "Use a successfully trained res_id owned by this workspace; return a complete MP3 with an expiring HTTPS URL."),
    },
    "iflytek-contract-intelligence-review": {
        "review": ("Submit a contract for review", "Accept HTTPS TXT, Markdown, DOCX, PDF, PNG or JPEG up to 20 MiB; at most 8 PDF pages and 4000 extracted characters. Generate selected reports using OCR, rules and model review as needed; human review remains necessary."),
        "get_review": ("Query contract review", "Return review status and completed findings with expiring Markdown or JSON report URLs."),
    },
    "animated-sketch-diagram": {
        "render_html_to_gif": ("Render HTML animation to GIF", "Render supplied HTML/SVG/CSS in an isolated container. Scripts, external resources and local file references are rejected; no natural-language diagram generation is provided. Input is limited to 256 KiB, 2000 elements and 120 million pixel-frames."),
        "get_render": ("Query GIF rendering", "Return rendering state and the completed GIF's dimensions, frame count and expiring HTTPS URL."),
    },
}

JOB_DESCRIPTION = (
    " HTTP 200 is a task snapshot, not proof of completion. Save job_id and query at least 5 seconds apart "
    "with bounded polling. Inspect status, result and error_code; do not automatically resubmit submission_unknown."
)


def endpoint_for(skill, action, request_model):
    async def invoke(request, payload):
        return await request.app.state.runtime.execute(request.state.principal, skill, action, payload)

    if request_model is not None:
        async def endpoint(request: Request, payload):
            return await invoke(request, payload.model_dump())
        endpoint.__annotations__["payload"] = request_model
    elif action == "list_voices":
        async def endpoint(request: Request):
            return await invoke(request, {})
    elif action == "get_training_text":
        async def endpoint(request: Request, text_id: int = Query(5001, gt=0, description="Provider training text set ID; 5001 is the common set.")):
            return await invoke(request, {"text_id": text_id})
    else:
        async def endpoint(request: Request, job_id: Annotated[m.JobId, Query(description="Backend job ID returned by this workspace's creation operation.")]):
            return await invoke(request, {"job_id": job_id})
    endpoint.__name__ = Tool(skill, action).operation_id
    return endpoint


def attach_tools(app):
    for skill, actions in CONTRACTS.items():
        for action, (request_model, response_model) in actions.items():
            summary, description = DESCRIPTIONS[skill][action]
            if issubclass(response_model, m.Job):
                description += JOB_DESCRIPTION
            if request_model is not None and issubclass(request_model, m.Submission):
                description += " Reuse request_id and identical parameters when retrying the same operation."
            register_tool(app, skill, action, endpoint_for(skill, action, request_model),
                          response_model=response_model, summary=summary, description=description)
