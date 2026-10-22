"""Attach the 24 concrete tools to the fixed catalog, with typed HTTP contracts."""

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
        async def endpoint(request: Request, text_id: int = Query(5001, gt=0)):
            return await invoke(request, {"text_id": text_id})
    else:
        async def endpoint(request: Request, job_id: m.JobId):
            return await invoke(request, {"job_id": job_id})
    endpoint.__name__ = Tool(skill, action).operation_id
    return endpoint


def attach_tools(app):
    for skill, actions in CONTRACTS.items():
        for action, (request_model, response_model) in actions.items():
            register_tool(app, skill, action, endpoint_for(skill, action, request_model), response_model=response_model)
