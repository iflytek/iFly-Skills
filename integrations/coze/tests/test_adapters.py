"""Use original Skill clients with replaced transports and synthetic media."""

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import adapters, compat
from app.contract_llm import parse_review
from app.errors import ErrorCode, ServiceError
from app.files import FileAccessError
from app.media import inspect_file
from app.models import Render, Translate
from app.render import container_command, validate_html


@pytest.fixture(autouse=True)
def synthetic_credentials(monkeypatch):
    for suffix in ("APP_ID", "API_KEY", "API_SECRET"):
        monkeypatch.setenv("IFLY_" + suffix, "test-only-" + suffix)
        monkeypatch.setenv("IFLY_CONTRACT_" + suffix, "test-contract-" + suffix)


def source_module(monkeypatch, skill):
    module = adapters.module(skill)
    monkeypatch.setattr(adapters, "module", lambda _: module)
    return module


def fake_input(monkeypatch, tmp_path, suffix=".png"):
    path = tmp_path / ("synthetic" + suffix)
    path.write_bytes(b"synthetic input")
    @contextmanager
    def input_file(*args, **kwargs):
        yield SimpleNamespace(path=path, size_bytes=path.stat().st_size, mime_type="image/png")
    monkeypatch.setattr(adapters, "input_file", input_file)
    return path


def test_translation_reuses_original_body_signing_and_result_parser(monkeypatch):
    module = source_module(monkeypatch, "iflytek-translate")
    calls = []
    def post(url, body, headers):
        calls.append((url, json.loads(body), headers))
        return {"code": 0, "data": {"result": {"from": "en", "to": "cn", "trans_result": {"src": "hello", "dst": "你好"}}}}
    monkeypatch.setattr(module, "_http_post", post)
    result = adapters.invoke("iflytek-translate", "translate", {"text": "hello", "from_lang": "en", "to_lang": "cn"})
    assert result == {"src": "hello", "dst": "你好", "from_lang": "en", "to_lang": "cn"}
    assert calls[0][1]["business"] == {"from": "en", "to": "cn"}
    assert calls[0][1]["common"]["app_id"] == "test-only-APP_ID"


def test_proofread_checks_both_envelopes_and_preserves_checklist(monkeypatch):
    import base64
    inner = {"code": 200, "data": {"checklist": [{"word": "x", "offset": 3, "suggest": "y"}]}}
    def post(*args):
        return {"header": {"code": 0}, "payload": {"output_result": {"text": base64.b64encode(json.dumps(inner).encode()).decode()}}}
    monkeypatch.setattr(compat, "proofread_post", post)
    result = adapters.invoke("iflytek-text-proofread", "check", {"text": "test"})
    assert result["checklist"] == inner["data"]["checklist"]
    inner["code"] = 500
    with pytest.raises(ServiceError):
        adapters.invoke("iflytek-text-proofread", "check", {"text": "test"})


def test_invoice_decodes_structured_fields_and_never_returns_error_as_success(monkeypatch, tmp_path):
    import base64
    module = source_module(monkeypatch, "iflytek-ocr-invoice")
    fake_input(monkeypatch, tmp_path)
    raw = {"header": {"code": 0}, "payload": {"output_text_result": {"text": base64.b64encode(b'{"total":"10.00"}').decode()}}}
    monkeypatch.setattr(module, "recognize_invoice", lambda *args: raw)
    assert adapters.invoke("iflytek-ocr-invoice", "recognize", {"image_url": "https://example.test/invoice.png"}) == {"result": {"total": "10.00"}}
    raw["header"]["code"] = 11200
    with pytest.raises(ServiceError) as error:
        adapters.invoke("iflytek-ocr-invoice", "recognize", {"image_url": "https://example.test/invoice.png"})
    assert error.value.code == ErrorCode.UPSTREAM_PERMISSION_DENIED


def test_image_ocr_reuses_request_and_correct_host_signature(monkeypatch, tmp_path):
    import base64
    module = source_module(monkeypatch, "iflytek-pdf-image-ocr")
    path = fake_input(monkeypatch, tmp_path)
    captured = []
    def post(url, **kwargs):
        captured.append((url, kwargs))
        return SimpleNamespace(json=lambda: {"header": {"code": 0}, "payload": {"result": {"text": base64.b64encode(b'{"text":"ABC"}').decode()}}})
    monkeypatch.setattr(module.requests, "post", post)
    assert adapters.image_ocr(path, "json", ("app", "key", "secret")) == {"json": {"text": "ABC"}}
    from urllib.parse import urlsplit, parse_qs
    parsed = urlsplit(captured[0][0])
    assert parse_qs(parsed.query)["host"] == [parsed.netloc]


def test_image_ocr_extracts_markdown_from_service_document(monkeypatch, tmp_path):
    formats = []
    def ocr(path, fmt):
        formats.append(fmt)
        return {"text": json.dumps({"document": [{"name": "markdown", "value": "# Invoice\nTotal 10.00"}], "image": []})}
    monkeypatch.setattr(compat, "image_ocr_client", lambda *args: SimpleNamespace(ocr=ocr))
    assert adapters.image_ocr(tmp_path / "image.png", "markdown", ("a", "b", "c")) == {"markdown": "# Invoice\nTotal 10.00"}
    assert formats == ["json,markdown"]
    result = adapters.image_ocr(tmp_path / "image.png", "json,markdown", ("a", "b", "c"))
    assert result["json"]["image"] == [] and result["markdown"].startswith("# Invoice")
    monkeypatch.setattr(compat, "image_ocr_client", lambda *args: SimpleNamespace(ocr=lambda *args: {"text": '{"document":[{"name":"markdown","value":""}]}'}))
    with pytest.raises(ServiceError):
        adapters.image_ocr(tmp_path / "image.png", "markdown", ("a", "b", "c"))
    assert adapters.image_ocr(tmp_path / "image.png", "markdown", ("a", "b", "c"), allow_empty=True) == {"markdown": ""}


def test_pdf_output_uses_https_omits_source_and_copies_duplicate_once(monkeypatch, tmp_path):
    from app.files import ArtifactStore
    seen = []
    path = tmp_path / "result.md"
    path.write_text("# Result", encoding="utf-8")
    @contextmanager
    def download(self, url):
        seen.append(url)
        if not url.startswith("https://"):
            raise FileAccessError("HTTPS required")
        yield SimpleNamespace(path=path, mime_type="text/markdown")
    monkeypatch.setattr(adapters.FileDownloader, "download", download)
    monkeypatch.setattr(adapters, "artifact_store", lambda: ArtifactStore(tmp_path / "artifacts", "https://example.test"))
    url = "http://bjcdn.openstorage.cn/result.md"
    result, artifacts = adapters.copy_outputs({"downUrl": url, "pages": [{"downUrl": url}], "sourceUrl": "http://private.invalid/input.pdf"})
    assert seen == ["https://bjcdn.openstorage.cn/result.md"]
    assert len(artifacts) == 1 and result["downUrl"] == result["pages"][0]["downUrl"]
    assert "sourceUrl" not in result
    with pytest.raises(ServiceError) as error:
        adapters.copy_outputs({"downUrl": "http://unverified.example.test/result.md"})
    assert error.value.code == ErrorCode.UPSTREAM_PROTOCOL_ERROR


def test_transcription_rejects_unsupported_task_type_before_submission():
    from app.models import TranscriptionSubmission
    valid = {"request_id": "request", "audio_url": "https://example.test/audio.mp3"}
    assert TranscriptionSubmission(**valid).language == "zh_cn"
    for fields in ({"language": "en_us"}, {"accent": "english"}, {"domain": "unknown"}):
        with pytest.raises(ValueError):
            TranscriptionSubmission(**valid, **fields)


def test_video_distinguishes_quota_rejection_from_permission_failure():
    client = compat.video_client(adapters.module("iflytek-video-translate"), "key", "secret")
    for code, expected in [(10009, ErrorCode.UPSTREAM_QUOTA_EXCEEDED), (11200, ErrorCode.UPSTREAM_PERMISSION_DENIED)]:
        response = SimpleNamespace(status_code=403, json=lambda: {"code": code, "message": "private upstream details"})
        with pytest.raises(ServiceError) as error:
            client._handle_response(response)
        assert error.value.code == expected


def test_training_failure_reports_known_reason_without_provider_details(monkeypatch):
    raw = {"code": 0, "flag": True, "data": {"trainStatus": 0, "failedDesc": "音频内容和文本相似度过低", "appId": "private-app"}}
    monkeypatch.setattr(compat, "voice_training_client", lambda *args: SimpleNamespace(get_task_status=lambda _: raw))
    result = adapters.invoke("iflytek-voiceclone-tts", "get_training", {"upstream_id": "training"})
    assert result["status"] == "failed" and result["result"]["failure_reason"] == "audio_text_mismatch"
    assert "private-app" not in json.dumps(result)
    raw["data"]["failedDesc"] = "unrecognized message with private details"
    assert "failure_reason" not in adapters.invoke("iflytek-voiceclone-tts", "get_training", {"upstream_id": "training"})["result"]


def test_training_wav_enforces_provider_media_requirements(tmp_path):
    import wave
    path = tmp_path / "sample.wav"
    def write(rate=24000, duration=1, channels=1, width=2):
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(channels)
            stream.setsampwidth(width)
            stream.setframerate(rate)
            stream.writeframes(b"\0" * int(rate * duration * channels * width))
    write()
    assert inspect_file(path, "sample") == (".wav", "audio/wav")
    for params in ({"rate": 22050}, {"duration": 41}, {"channels": 2}, {"width": 1}):
        write(**params)
        with pytest.raises(FileAccessError):
            inspect_file(path, "sample")


def test_renderer_accepts_document_language_and_utf8_but_not_meta_refresh():
    validate_html('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Diagram</title></head><body><div>Test</div></body></html>')
    for meta in ('<meta http-equiv="refresh" content="0;url=https://example.test">', '<meta charset="utf-7">', '<meta>'):
        with pytest.raises(ValueError):
            validate_html(meta)


def test_image_understanding_requires_final_frame_and_retains_usage(monkeypatch, tmp_path):
    module = source_module(monkeypatch, "iflytek-image-understanding")
    path = fake_input(monkeypatch, tmp_path)
    frames = [{"header": {"code": 0}, "payload": {"choices": {"status": 1, "text": [{"content": "partial"}]}}}]
    monkeypatch.setattr(module, "ws_communicate", lambda *args: [json.dumps(f) for f in frames])
    params = {"question": "what?", "domain": "imagev3", "temperature": 0.5, "max_tokens": 32}
    with pytest.raises(ServiceError):
        adapters.analyze(path, params, ("app", "key", "secret"))
    frames.append({"header": {"code": 0}, "payload": {"choices": {"status": 2, "text": [{"content": " answer"}]}, "usage": {"text": {"total_tokens": 7}}}})
    result = adapters.analyze(path, params, ("app", "key", "secret"))
    assert result == {"text": "partial answer", "usage": {"total_tokens": 7}}


def test_hyper_tts_partial_audio_is_never_success(monkeypatch, tmp_path):
    module = adapters.module("iflytek-hyper-tts")
    class Socket:
        def send(self, data):
            pass
        def recv(self):
            return ""
        def close(self):
            pass
    monkeypatch.setattr(module.websocket, "create_connection", lambda *args, **kwargs: Socket())
    with pytest.raises(RuntimeError, match="final audio frame"):
        compat.hyper_synthesize(module, module.XfeiHyperTTSClient("app", "key", "secret"), text="hello", output_path=str(tmp_path / "audio.mp3"))


@pytest.mark.parametrize("status,expected", [("WAITING", "running"), ("FINISH", "succeeded"), ("ANY_FAILED", "partially_succeeded"), ("FAILED", "failed")])
def test_pdf_preserves_partial_failure(monkeypatch, status, expected):
    client = SimpleNamespace(query_status=lambda _: {"data": {"status": status, "failedPages": [2]}})
    monkeypatch.setattr(adapters, "module", lambda _: SimpleNamespace(IflyPdfOCRClient=lambda *args: client))
    result = adapters.invoke("iflytek-pdf-image-ocr", "get_pdf_task", {"upstream_id": "pdf-upstream"})
    assert result["status"] == expected
    if status == "ANY_FAILED":
        assert result["result"]["details"]["failedPages"] == [2]


def test_transcription_uses_single_query_and_original_lattice_parser(monkeypatch):
    module = source_module(monkeypatch, "iflytek-speed-transcription")
    raw = {"data": {"task_status": "3", "result": {"lattice": [{"begin": "0", "end": "500", "spk": "speaker-0",
        "json_1best": {"st": {"rt": [{"ws": [{"cw": [{"w": "hello", "wp": "n"}]}]}]}}}]}}}
    calls = []
    def query(self, task):
        calls.append(task)
        return raw
    monkeypatch.setattr(module.XfeiSpeedTranscription, "query_task", query)
    result = adapters.invoke("iflytek-speed-transcription", "get_task", {"upstream_id": "upstream"})
    assert calls == ["upstream"]
    assert result["result"]["text"] == "hello"
    assert result["result"]["segments"][0]["end"] == "500"
    raw["data"]["task_status"] = "unexpected"
    with pytest.raises(ServiceError):
        adapters.invoke("iflytek-speed-transcription", "get_task", {"upstream_id": "upstream"})


def test_training_transport_is_https_and_upload_does_not_submit(monkeypatch):
    import urllib.request
    module = adapters.module("iflytek-voiceclone-tts")
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"code":0,"flag":true,"data":{}}'
    def open_request(self, request, **kwargs):
        requests.append(request)
        return Response()
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", open_request)
    client = compat.voice_training_client(module, "app", "key")
    client.token = "synthetic-token"
    client.upload_audio_url("task", "https://files.example.test/input.wav", 5001, 1)
    assert len(requests) == 1
    assert requests[0].full_url == "https://opentrain.xfyousheng.com/voice_train/audio/v1/add"
    assert json.loads(requests[0].data)["textSegId"] == 1
    with pytest.raises(RuntimeError):
        compat._NoTrainingRedirect().redirect_request(None, None, 302, None, None, "https://other.test/")
    with pytest.raises(ServiceError) as error:
        client._raise_for_api_error({"code": 10021}, "/task/submit")
    assert error.value.code == ErrorCode.UPSTREAM_QUOTA_EXCEEDED


def test_voice_stream_disconnect_is_rejected_with_verified_tls_transport(monkeypatch):
    import websocket
    module = adapters.module("iflytek-voiceclone-tts")
    options = []
    class Socket:
        def send(self, value): pass
        def recv(self): return ""
        def close(self): pass
    def connect(url, **kwargs):
        assert url.startswith("wss://")
        options.append(kwargs)
        return Socket()
    monkeypatch.setattr(websocket, "create_connection", connect)
    client = module.VoiceCloneSynthesizer("app", "key", "secret", "resource", SimpleNamespace(format="mp3", sample_rate=16000, speed=50, volume=50, pitch=50))
    with pytest.raises(RuntimeError, match="final audio frame"):
        compat.voice_synthesize(module, client, "hello")
    assert "sslopt" not in options[0]  # websocket-client's certificate verification remains enabled.


@pytest.mark.parametrize("html", ["<script>fetch('/')</script>", '<img src="file:///secret">',
    '<div style="background:url(https://example.test/x)">x</div>', '<style>@import "x";</style>',
    '<div onclick="alert(1)">x</div>', '<iframe src="https://example.test"></iframe>',
    '<style>div{background:u\\72l(x)}</style>'])
def test_render_rejects_scripts_files_and_network_references(html):
    with pytest.raises(ValueError):
        validate_html(html)


def test_render_limits_and_container_boundary():
    validate_html('<style>@keyframes move{to{transform:translateX(10px)}}</style><div style="animation:move 1s infinite">x</div>')
    with pytest.raises(ValueError):
        Render(request_id="test", html="<div>x</div>", width=1600, height=1200, scale=2, loop_ms=5000)
    args = container_command("docker", "sha256:" + "a" * 64, "synthetic")
    assert {"--network=none", "--read-only", "--cap-drop=ALL", "--user=10001:10001", "--pull=never"} <= set(args)
    assert not {"-v", "--mount", "--privileged", "--env", "-e"} & set(args)
    with pytest.raises(ServiceError):
        container_command("docker", "unverified:latest", "synthetic")


def test_media_decodes_images_and_rejects_legacy_doc(tmp_path):
    from PIL import Image
    path = tmp_path / "input"
    Image.new("RGB", (16, 16), "white").save(path, format="PNG")
    assert inspect_file(path, "image") == (".png", "image/png")
    path.write_bytes(b"fake document")
    with pytest.raises(FileAccessError):
        inspect_file(path, "contract", "https://example.test/legacy.doc")


def test_model_review_requires_grounded_evidence():
    result = {"summary": "summary", "key_clauses": [], "suggestions": [],
              "risks": [{"title": "risk", "level": "high", "evidence": "invented", "suggestion": "verify"}]}
    with pytest.raises(RuntimeError):
        parse_review(json.dumps(result), "actual contract")
    result["risks"][0]["evidence"] = "actual contract"
    assert parse_review(json.dumps(result), "actual contract").risks[0]["source"] == "model_inference"


def test_contract_real_processors_reports_and_required_translation(monkeypatch, tmp_path):
    from app import contract
    from app.files import ArtifactStore
    source = tmp_path / "contract.txt"
    source.write_text("第一条 付款。甲方应在收到发票后三十日支付款项。\n第二条 责任。乙方承担无限责任，甲方保留单方解除权。", encoding="utf-8")
    @contextmanager
    def input_file(*args, **kwargs):
        yield SimpleNamespace(path=source)
    monkeypatch.setattr(contract, "input_file", input_file)
    monkeypatch.setattr(contract, "artifact_store", lambda: ArtifactStore(tmp_path / "artifacts", "https://example.test"))
    monkeypatch.setattr(contract.LLMReviewClient, "review_contract", lambda *args: SimpleNamespace(summary="summary", risks=[], key_clauses=[], suggestions=[]))
    params = {"file_url": "https://example.test/contract.txt", "lang": "zh", "review_mode": "standard", "focus": [], "need_translation": False, "output_format": "json"}
    result = contract.review(params)
    assert result["review"]["clauses"]
    assert [r["mime_type"] for r in result["reports"]] == ["application/json"]
    assert result["review"]["extraction_quality"]["confidence"] is None
    def fail_translation(*args):
        raise ServiceError(ErrorCode.UPSTREAM_ERROR)
    monkeypatch.setattr(contract, "translate", fail_translation)
    with pytest.raises(ServiceError):
        contract.review({**params, "need_translation": True})
    with pytest.raises(ServiceError):
        contract.review({**params, "review_mode": "deep"})
    result = contract.review({**params, "output_format": "both"})
    assert {r["mime_type"] for r in result["reports"]} == {"application/json", "text/markdown"}


def test_utf8_translation_limit_is_not_character_limit():
    Translate(text="字" * 1365)
    with pytest.raises(ValueError):
        Translate(text="字" * 1366)
