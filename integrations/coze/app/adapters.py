"""Fixed adapters over repository Skill clients, run only inside the worker."""

from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import urlsplit

from . import compat
from .errors import ErrorCode, ServiceError
from .execution import MEDIA_DOWNLOAD_TIMEOUT_SECONDS
from .files import ArtifactStore, FileAccessError, FileDownloader, FilePolicy
from .media import input_file

SOURCES = {
    "iflytek-translate": "translate.py",
    "iflytek-text-proofread": "text_proofread.py",
    "iflytek-ocr-invoice": "invoice.py",
    "iflytek-hyper-tts": "xfei_hyper_tts.py",
    "iflytek-pdf-image-ocr": "image_ocr.py",
    "pdf": "pdf_ocr.py",
    "iflytek-speed-transcription": "transcribe.py",
    "iflytek-image-understanding": "image_understanding.py",
    "iflytek-video-translate": "xfei_video_translate.py",
    "iflytek-voiceclone-tts": "voiceclone.py",
}
SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills"


def module(skill):
    directory = "iflytek-pdf-image-ocr" if skill == "pdf" else skill
    path = SKILLS_ROOT / directory / "scripts" / SOURCES[skill]
    spec = importlib.util.spec_from_file_location("coze_" + skill.replace("-", "_"), path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def credentials(prefix="IFLY", fields=("APP_ID", "API_KEY", "API_SECRET")):
    values = tuple(os.environ.get(prefix + "_" + field, "") for field in fields)
    if not all(value.strip() for value in values):
        raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return values


def artifact_store():
    base = os.environ.get("COZE_ARTIFACT_BASE_URL", "")
    root = os.environ.get("COZE_DATA_DIR", "")
    if not base or not root:
        raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return ArtifactStore(Path(root), base)


def protocol(condition):
    if not condition:
        raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR)


def upstream_code(code, success=0):
    if code == success:
        return
    # Shared documented authentication/authorization and quota categories only.
    if str(code) in {"11200", "10313"}:
        raise ServiceError(ErrorCode.UPSTREAM_PERMISSION_DENIED)
    if str(code) == "10010":
        raise ServiceError(ErrorCode.UPSTREAM_QUOTA_EXCEEDED)
    raise ServiceError(ErrorCode.UPSTREAM_ERROR)


def remote_id(value):
    protocol(isinstance(value, (str, int)) and not isinstance(value, bool)
             and re.fullmatch(r"[A-Za-z0-9_-]{1,256}", str(value)))
    return str(value)


def translate(payload, creds):
    from .models import Translate
    try:
        Translate.model_validate(payload)
    except ValueError:
        raise ServiceError(ErrorCode.INVALID_REQUEST) from None
    m = module("iflytek-translate")
    source, target = m._normalize_lang(payload["from_lang"]), m._normalize_lang(payload["to_lang"])
    if not source or not target:
        raise ServiceError(ErrorCode.INVALID_REQUEST)
    body = m._build_body(creds[0], payload["text"], source, target)
    response = m._http_post(m.URL, body, m._build_headers(creds[1], creds[2], body))
    upstream_code(response.get("code"))
    parsed, error = m._parse_result(response)
    protocol(not error and isinstance(parsed, dict) and isinstance(parsed.get("dst"), str) and bool(parsed["dst"]))
    return {"src": parsed.get("src", payload["text"]), "dst": parsed["dst"],
            "from_lang": parsed.get("from") or source, "to_lang": parsed.get("to") or target}


def analyze(path, payload, creds):
    m = module("iflytek-image-understanding")
    messages = [{"role": "user", "content": m.read_image_base64(str(path)), "content_type": "image"},
                {"role": "user", "content": payload["question"], "content_type": "text"}]
    params = m.gen_params(creds[0], messages, payload["domain"], payload["temperature"], payload["max_tokens"])
    frames = [json.loads(frame) for frame in m.ws_communicate(m.build_auth_url(m.WS_URL, creds[1], creds[2]), json.dumps(params))]
    protocol(bool(frames))
    text = []
    for frame in frames:
        upstream_code(frame.get("header", {}).get("code"))
        choices = frame.get("payload", {}).get("choices", {})
        protocol(choices.get("status") in {0, 1, 2})
        text.extend(item["content"] for item in choices.get("text", []))
    protocol(choices["status"] == 2 and bool("".join(text)))
    return {"text": "".join(text), "usage": frames[-1].get("payload", {}).get("usage", {}).get("text", {})}


def image_ocr(path, fmt, creds, *, allow_empty=False):
    m = module("iflytek-pdf-image-ocr")
    # The service accepts json or json,markdown, but not markdown alone.
    result = compat.image_ocr_client(m, *creds).ocr(str(path), "json,markdown" if fmt == "markdown" else fmt)
    text = result.get("text")
    protocol(isinstance(text, str) and bool(text))
    try:
        structured = json.loads(text)
    except ValueError:
        raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR) from None
    protocol(isinstance(structured, dict))
    if fmt == "json":
        return {"json": structured}
    documents = structured.get("document")
    protocol(isinstance(documents, list))
    markdown = [item.get("value") for item in documents if isinstance(item, dict) and item.get("name") == "markdown"]
    protocol(bool(markdown) and all(isinstance(value, str) for value in markdown))
    markdown = "\n".join(markdown)
    protocol(bool(markdown.strip()) or allow_empty)
    if fmt == "markdown":
        return {"markdown": markdown}
    return {"json": structured, "markdown": markdown}


def staged(status, result=None, upstream_id=None, error_code=None):
    return {"status": status, "result": result, "upstream_id": upstream_id, "error_code": error_code}


def copy_outputs(value):
    """Rehost provider result links as expiring capabilities; omit internal task IDs."""
    artifacts = []
    copied = {}
    def clean(item, key=""):
        if isinstance(item, dict):
            return {k: clean(v, k) for k, v in item.items()
                    if k not in {"taskNo", "task_id", "taskId", "file_url", "pdfUrl", "audioUrl", "sourceUrl"}}
        if isinstance(item, list):
            return [clean(v, key) for v in item]
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            if item in copied:
                return copied[item]
            parts = urlsplit(item)
            # PDF results currently advertise HTTP on this provider CDN. Its HTTPS
            # endpoint is verified; never fetch over HTTP or follow a downgrade.
            url = parts._replace(scheme="https").geturl() if (
                parts.scheme == "http" and parts.netloc == "bjcdn.openstorage.cn") else item
            try:
                with FileDownloader(FilePolicy(max_bytes=128 * 1024 * 1024,
                                               timeout_seconds=MEDIA_DOWNLOAD_TIMEOUT_SECONDS)).download(url) as downloaded:
                    artifact = asdict(artifact_store().put_file(downloaded.path, downloaded.mime_type))
            except FileAccessError:
                raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR) from None
            artifacts.append(artifact)
            copied[item] = artifact["url"]
            return artifact["url"]
        return item
    return clean(value), artifacts


def invoke(skill, action, payload):
    p = {key: value for key, value in payload.items() if key not in {"request_id", "job_id"}}
    if skill == "animated-sketch-diagram":
        from .render import render
        return staged("succeeded", render(p))
    if skill == "iflytek-contract-intelligence-review":
        from .contract import review
        return staged("succeeded", review(p))
    if action == "list_voices":
        m = module(skill)
        return {"free_voices": m.FREE_VOICES, "all_voices": m.VOICE_LIST}
    if skill == "iflytek-translate":
        return translate(p, credentials())
    if skill == "iflytek-text-proofread":
        m = module(skill)
        app, key, secret = credentials()
        response = compat.proofread_post(m, m._build_auth_url(m.API_URL, key, secret), m._build_body(app, p["text"]), app)
        upstream_code(response.get("header", {}).get("code"))
        result = m._parse_result(response)
        upstream_code(result.get("code"), 200)
        checklist = result.get("data", {}).get("checklist")
        protocol(isinstance(checklist, list))
        return {"checklist": checklist}
    if skill == "iflytek-ocr-invoice":
        creds = credentials()
        with input_file(p["image_url"], "image") as source:
            m = module(skill)
            raw = m.recognize_invoice(str(source.path), *creds)
            upstream_code(raw.get("header", {}).get("code"))
            result = json.loads(m.extract_result(raw))
        protocol(isinstance(result, (dict, list)))
        return {"result": result}
    if skill == "iflytek-image-understanding":
        creds = credentials()
        with input_file(p.pop("image_url"), "image") as source:
            return analyze(source.path, p, creds)
    if skill == "iflytek-hyper-tts":
        creds, store = credentials(), artifact_store()
        m = module(skill)
        output = Path("speech.mp3")
        compat.hyper_synthesize(m, m.XfeiHyperTTSClient(*creds), output_path=str(output), encoding="lame", **p)
        from .media import inspect_file
        inspect_file(output, "mp3")
        return {"audio": asdict(store.put_file(output, "audio/mpeg")), "sample_rate": p["sample_rate"], "format": "mp3"}
    if skill == "iflytek-pdf-image-ocr":
        if action == "recognize_image":
            creds = credentials()
            with input_file(p["image_url"], "image") as source:
                return {"result": image_ocr(source.path, p["format"], creds)}
        client = module("pdf").IflyPdfOCRClient(*credentials(fields=("APP_ID", "API_SECRET")))
        if action == "create_pdf_task":
            with input_file(p["pdf_url"], "pdf", max_bytes=32 * 1024 * 1024) as source:
                data = client.start_task(pdf_path=source.path, export_format=p["export_format"])["data"]
            return staged("running", {"upstream_status": str(data.get("status", "WAITING"))}, remote_id(data.get("taskNo")))
        data = client.query_status(p["upstream_id"])["data"]
        status = data.get("status")
        protocol(status in {"FINISH", "ANY_FAILED", "FAILED", "DOING", "WAITING"})
        details, artifacts = copy_outputs(data) if status in {"FINISH", "ANY_FAILED"} else ({}, [])
        return staged({"FINISH": "succeeded", "ANY_FAILED": "partially_succeeded", "FAILED": "failed"}.get(status, "running"),
                      {"upstream_status": status, "details": details, "artifacts": artifacts},
                      error_code="UPSTREAM_ERROR" if status == "FAILED" else None)
    if skill == "iflytek-speed-transcription":
        m = module(skill)
        client = compat.transcription_client(m, *credentials())
        if action == "create_task":
            with input_file(p.pop("audio_url"), "mp3", max_bytes=128 * 1024 * 1024,
                            timeout_seconds=MEDIA_DOWNLOAD_TIMEOUT_SECONDS) as source:
                url = (client.upload_small_file if source.size_bytes < 31457280 else client.upload_large_file)(source.path)
                upstream_id = client.create_task(url, file_path=source.path, **p)
            return staged("running", {"upstream_status": 1}, remote_id(upstream_id))
        raw = client.query_task(p["upstream_id"])
        status = str(raw.get("data", {}).get("task_status"))
        protocol(status in {"-1", "1", "2", "3", "4"})
        result = {"upstream_status": int(status)}
        if status in {"3", "4"}:
            parsed = client._parse_result(raw)
            result.update(text=parsed["text"], segments=parsed["segments"])
        return staged("succeeded" if status in {"3", "4"} else "failed" if status == "-1" else "running", result,
                      error_code="UPSTREAM_ERROR" if status == "-1" else None)
    if skill == "iflytek-video-translate":
        client = compat.video_client(module(skill), *credentials(fields=("API_KEY", "API_SECRET")))
        if action == "create_task":
            store = artifact_store()
            with input_file(p["video_url"], "video", max_bytes=128 * 1024 * 1024,
                            timeout_seconds=MEDIA_DOWNLOAD_TIMEOUT_SECONDS) as source:
                url = store.put_file(source.path, source.mime_type, ttl_seconds=86400).url + "/input.mp4"
            data = client.create_task(url, p["src_lang"], p["dest_lang"], p["name"] or None)
            return staged("running", {"upstream_status": str(data.get("status", "waiting_parsing"))}, remote_id(data.get("task_id")))
        if action == "confirm_transcript":
            client.confirm_transcript(p["upstream_id"], force_rerun=False)
            return staged("running", {"upstream_status": "transcript_confirmed"})
        data = client.get_task(p["upstream_id"])
        status = data.get("status")
        protocol(isinstance(status, str) and bool(status))
        state = {"completed": "succeeded", "failed": "failed", "cancelled": "failed",
                 "waiting_transcript_confirmation": "waiting_input",
                 "waiting_manual_intervention_segment": "waiting_input",
                 "waiting_manual_intervention_refine": "waiting_input"}.get(status, "running")
        if state == "succeeded":
            protocol(isinstance(data.get("output"), dict) and bool(data["output"].get("output_video_url")))
        # Keep new provider stages visible without treating them as completion.
        details, artifacts = copy_outputs({k: v for k, v in data.items() if k in {"output", "segments"}}) if state == "succeeded" else ({}, [])
        return staged(state, {"upstream_status": status, "details": details, "artifacts": artifacts},
                      error_code="UPSTREAM_ERROR" if state == "failed" else None)
    if skill == "iflytek-voiceclone-tts":
        m = module(skill)
        if action == "synthesize":
            creds, store = credentials(), artifact_store()
            client = m.VoiceCloneSynthesizer(*creds, p["res_id"], SimpleNamespace(**p))
            audio = compat.voice_synthesize(m, client, p["text"])
            protocol(bool(audio))
            output = Path("cloned.mp3")
            output.write_bytes(audio)
            from .media import inspect_file
            inspect_file(output, "mp3")
            return {"audio": asdict(store.put_file(output, "audio/mpeg")), "sample_rate": p["sample_rate"], "format": "mp3"}
        client = compat.voice_training_client(m, *credentials(fields=("APP_ID", "API_KEY")))
        if action == "get_training_text":
            raw = client.get_training_text(p["text_id"])
        elif action == "create_training":
            raw = client.create_task(**p)
        elif action == "upload_sample":
            store = artifact_store()
            with input_file(p["audio_url"], "sample", max_bytes=3 * 1024 * 1024) as source:
                url = store.put_file(source.path, source.mime_type, ttl_seconds=86400).url + "/input" + source.path.suffix
            raw = client.upload_audio_url(p["upstream_id"], url, p["text_id"], p["seg_id"])
        elif action == "submit_training":
            raw = client.submit_task(p["upstream_id"])
        else:
            raw = client.get_task_status(p["upstream_id"])
        upstream_code(raw.get("code"))
        protocol(raw.get("flag") is True)
        data = raw.get("data")
        if action == "get_training_text":
            protocol(isinstance(data, (list, dict)))
            return {"text_id": p["text_id"], "segments": data}
        if action == "create_training":
            value = data.get("taskId") if isinstance(data, dict) else data
            return staged("waiting_input", {"stage": "created"}, remote_id(value))
        if action == "upload_sample":
            return staged("waiting_input", {"stage": "sample_uploaded"})
        if action == "submit_training":
            return staged("running", {"stage": "submitted"})
        protocol(isinstance(data, dict) and "trainStatus" in data)
        state = str(data["trainStatus"])
        protocol(state in {"-1", "0", "1", "2"})
        if state == "1":
            return staged("succeeded", {"stage": "trained", "upstream_status": state, "res_id": remote_id(data.get("assetId"))})
        result = {"stage": "failed" if state == "0" else "submitted", "upstream_status": state}
        if state == "0" and data.get("failedDesc") == "音频内容和文本相似度过低":
            result["failure_reason"] = "audio_text_mismatch"
        return staged("failed" if state == "0" else "running", result,
                      error_code="UPSTREAM_ERROR" if state == "0" else None)
    raise ServiceError(ErrorCode.NOT_FOUND)
