"""Exercise public routes, durable work and ownership without paid upstream calls."""

import asyncio
from email.message import Message
import json
import socket
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.catalog import SKILL_IDS, SKILL_TOOLS
from app.config import Principal, Settings, SiteGrant
from app.errors import ErrorCode, ServiceError
from app.main import create_app
from app.runtime import Runtime, RuntimeConfig
from app.runner import SkillRunner
from app.tasks import TaskStateError, TaskStore


KEY = "test-cn-" + "a" * 40
OTHER_KEY = "test-global-" + "b" * 40
CN = Principal("cn", "test-cn-space", SKILL_IDS)
GLOBAL = Principal("global", "test-global-space", SKILL_IDS)
SETTINGS = Settings((SiteGrant(CN, KEY), SiteGrant(GLOBAL, OTHER_KEY)))
HEADERS = {"X-API-Key": KEY}
TRANSCRIPTION = "iflytek-speed-transcription"
VOICE = "iflytek-voiceclone-tts"


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.error = None

    async def call(self, skill, action, payload, **kwargs):
        self.calls.append((skill, action, payload))
        if self.error:
            raise ServiceError(self.error)
        if action == "create_training":
            return {"status": "waiting_input", "upstream_id": "voice-upstream", "result": {"stage": "created"}}
        if action in {"upload_sample", "submit_training", "get_training"}:
            stage, status = {"upload_sample": ("sample_uploaded", "waiting_input"), "submit_training": ("submitted", "running"),
                             "get_training": ("trained", "succeeded")}[action]
            return {"status": status, "result": {"stage": stage, "res_id": "owned-resource" if stage == "trained" else None}}
        if action == "create_task":
            return {"status": "running", "upstream_id": "transcription-upstream", "result": {"upstream_status": 1}}
        if action == "get_task":
            return {"status": "succeeded", "result": {"upstream_status": 3, "text": "hello", "segments": []}}
        if action == "review":
            return {"status": "succeeded", "result": {"review": {"final_summary": "test finding"}, "reports": []}}
        if action == "translate":
            return {"src": payload["text"], "dst": "translated", "from_lang": "en", "to_lang": "cn"}
        raise AssertionError(action)


def path(skill, action):
    return f"/v1/skills/{skill}/{action}"


@pytest.fixture
def service(tmp_path):
    runner = FakeRunner()
    runtime = Runtime(RuntimeConfig(tmp_path, "https://files.example.test"), runner=runner)
    with TestClient(create_app(SETTINGS, runtime=runtime)) as client:
        yield client, runtime, runner


def age(runtime, job_id):
    with runtime.tasks._connect() as db:
        db.execute("UPDATE tasks SET updated_at = ? WHERE task_id = ?", (time.time() - 10, job_id))


def post(client, skill, action, payload):
    return client.post(path(skill, action), headers=HEADERS, json=payload)


@pytest.mark.parametrize("error_code", [ErrorCode.UPSTREAM_QUOTA_EXCEEDED, ErrorCode.UPSTREAM_PERMISSION_DENIED])
def test_explicit_upstream_rejection_is_failed_and_does_not_resubmit(service, error_code):
    client, runtime, runner = service
    runner.error = error_code
    payload = {"request_id": "rejected", "audio_url": "https://example.test/a.mp3"}
    first = post(client, TRANSCRIPTION, "create_task", payload).json()
    assert first["status"] == "failed" and first["error_code"] == error_code.value
    assert post(client, TRANSCRIPTION, "create_task", payload).json() == first
    assert len(runner.calls) == 1


def test_rejected_training_stage_keeps_parent_retryable_with_new_request_id(service):
    client, runtime, runner = service
    parent = post(client, VOICE, "create_training", {"request_id": "create", "name": "test", "sex": 2}).json()
    payload = {"request_id": "upload-1", "job_id": parent["job_id"], "audio_url": "https://example.test/sample.wav"}
    runner.error = ErrorCode.UPSTREAM_QUOTA_EXCEEDED
    assert post(client, VOICE, "upload_sample", payload).json()["error"]["code"] == "UPSTREAM_QUOTA_EXCEEDED"
    assert runtime.tasks.get_for_principal(parent["job_id"], CN).status == "waiting_input"
    runner.error = None
    assert post(client, VOICE, "upload_sample", {**payload, "request_id": "upload-2"}).json()["result"]["stage"] == "sample_uploaded"


def test_all_24_contracts_have_auth_models_and_bodyless_gets(service):
    client, _, _ = service
    schema = client.app.openapi()
    assert len(schema["paths"]) == 24
    for skill, actions in SKILL_TOOLS.items():
        for action in actions:
            definition = next(iter(schema["paths"][path(skill, action)].values()))
            assert definition["security"] == [{"ServiceApiKey": []}]
            assert definition["responses"]["200"]["content"]["application/json"]["schema"]
            if action.startswith("get_") or action == "list_voices":
                assert "requestBody" not in definition
            else:
                assert definition["requestBody"]["required"]


def test_submit_retries_are_deduplicated_and_cross_site_ids_are_hidden(service):
    client, runtime, runner = service
    body = {"request_id": "stable", "audio_url": "https://example.test/audio.mp3"}
    first = post(client, TRANSCRIPTION, "create_task", body)
    assert first.status_code == 200
    job = first.json()["job_id"]
    second = post(client, TRANSCRIPTION, "create_task", body)
    assert second.json() == first.json()
    assert len(runner.calls) == 1
    assert post(client, TRANSCRIPTION, "create_task", {**body, "audio_url": "https://example.test/changed.mp3"}).status_code == 409
    assert client.get(path(TRANSCRIPTION, "get_task"), params={"job_id": job}, headers={"X-API-Key": OTHER_KEY}).status_code == 404
    assert client.get(path("iflytek-video-translate", "get_task"), params={"job_id": job}, headers=HEADERS).status_code == 404
    assert client.get(path(TRANSCRIPTION, "get_task"), params={"job_id": job}, headers=HEADERS).json()["status"] == "running"
    assert len(runner.calls) == 1
    age(runtime, job)
    result = client.get(path(TRANSCRIPTION, "get_task"), params={"job_id": job}, headers=HEADERS).json()
    assert result["status"] == "succeeded" and result["result"]["text"] == "hello"
    assert "transcription-upstream" not in json.dumps(result)
    assert len(runner.calls) == 2


def test_video_waiting_polls_then_large_output_is_persisted_once(tmp_path, monkeypatch):
    from app import adapters, files, runtime as runtime_module, tasks

    clock = SimpleNamespace(now=1000.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now)
    for module in (files, runtime_module, tasks):
        monkeypatch.setattr(module, "time", fake_time)
    size = 128 * 1024 * 1024
    downloads = []

    class Response:
        status = 200
        def __init__(self):
            self.remaining = size
            self.headers = Message()
            self.headers["Content-Type"] = "video/mp4"
            self.headers["Content-Length"] = str(size)
        def read(self, amount):
            count = min(amount, self.remaining)
            self.remaining -= count
            clock.now += count / size * 120  # 128 MiB over two simulated minutes.
            return b"v" * count
        def close(self):
            pass

    class Opener:
        def open(self, request, timeout):
            downloads.append(request.full_url)
            return Response()

    def downloader(policy):
        return files.FileDownloader(policy, opener=Opener(), temp_root=tmp_path,
                                    resolver=lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])

    state = {"status": "waiting_transcript_confirmation"}
    url = "https://upstream.example/video.mp4"
    def query(_):
        if state["status"] == "completed":
            clock.now += 120  # Leave room for provider work as well as downloading.
        return {"status": state["status"], "output": {"output_video_url": url}, "segments": [{"url": url}]}
    client = SimpleNamespace(get_task=query, confirm_transcript=lambda *a, **k: None)
    monkeypatch.setattr(adapters, "module", lambda _: None)
    monkeypatch.setattr(adapters, "credentials", lambda **kw: ("test-key", "test-secret"))
    monkeypatch.setattr(adapters.compat, "video_client", lambda *a: client)
    monkeypatch.setattr(adapters, "FileDownloader", downloader)

    class Runner:
        def __init__(self):
            self.calls = []
        async def call(self, skill, action, payload, *, timeout=60):
            self.calls.append(action)
            if action == "create_task":
                return {"status": "running", "upstream_id": "video-1", "result": {"upstream_status": "processing"}}
            started = clock.now
            result = adapters.invoke(skill, action, payload)
            assert clock.now - started < timeout
            assert runtime.tasks.expire() == 0  # Active transfer must keep a valid lease.
            return result

    runner = Runner()
    runtime = Runtime(RuntimeConfig(tmp_path, "https://files.example.test"), runner=runner)
    monkeypatch.setattr(adapters, "artifact_store", lambda: runtime.artifacts)
    skill = "iflytek-video-translate"

    async def scenario():
        initial = await runtime.execute(CN, skill, "create_task", {"request_id": "video", "video_url": "https://input.example/video.mp4"})
        job = initial["job_id"]
        for _ in range(2):
            clock.now += 6
            waiting = await runtime.execute(CN, skill, "get_task", {"job_id": job})
            assert waiting["status"] == "waiting_input"
            assert waiting["result"]["artifacts"] == []
        assert downloads == []
        await runtime.execute(CN, skill, "confirm_transcript", {"request_id": "confirm", "job_id": job})
        state["status"] = "completed"
        clock.now += 6
        result = await runtime.execute(CN, skill, "get_task", {"job_id": job})
        assert result["status"] == "succeeded"
        artifact = result["result"]["artifacts"][0]
        assert artifact["size_bytes"] == size
        assert runtime.artifacts.resolve(artifact["artifact_id"])[0].stat().st_size == size
        assert downloads == [url]
        assert len(list(runtime.artifacts.data_root.iterdir())) == 1
        before = len(runner.calls)
        clock.now += 6
        assert await runtime.execute(CN, skill, "get_task", {"job_id": job}) == result
        assert len(runner.calls) == before
        assert not list(tmp_path.glob("coze-input-*"))

    asyncio.run(scenario())


@pytest.mark.parametrize("skill", ["iflytek-video-translate", TRANSCRIPTION])
@pytest.mark.parametrize("failure", [None, ErrorCode.TIMEOUT])
def test_slow_media_submission_retains_lease_and_idempotency(tmp_path, monkeypatch, skill, failure):
    from app import runtime as runtime_module, tasks
    clock = SimpleNamespace(now=1000.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now)
    monkeypatch.setattr(tasks, "time", fake_time)
    monkeypatch.setattr(runtime_module, "time", fake_time)

    class Runner:
        calls = 0
        async def call(self, skill, action, payload, *, timeout=60):
            self.calls += 1
            clock.now += timeout if failure else 240
            assert runtime.tasks.expire() == 0
            if failure:
                raise ServiceError(failure)
            assert timeout > 240
            return {"status": "running", "upstream_id": "media-id",
                    "result": {"upstream_status": "processing" if skill == "iflytek-video-translate" else 1}}

    runner = Runner()
    runtime = Runtime(RuntimeConfig(tmp_path), runner=runner)
    body = {"request_id": "slow", "video_url" if skill == "iflytek-video-translate" else "audio_url": "https://input.example/file"}
    async def scenario():
        result = await runtime.execute(CN, skill, "create_task", body)
        assert result["status"] == ("submission_unknown" if failure else "running")
        assert runtime.tasks.get_for_principal(result["job_id"], CN).lease_owner is None
        assert await runtime.execute(CN, skill, "create_task", body) == result
        assert runner.calls == 1
    asyncio.run(scenario())


def test_unknown_submission_is_durable_and_never_retried(service):
    client, runtime, runner = service
    runner.error = ErrorCode.TIMEOUT
    body = {"request_id": "uncertain", "audio_url": "https://example.test/a.mp3"}
    first = post(client, TRANSCRIPTION, "create_task", body).json()
    assert first["status"] == "submission_unknown"
    runner.error = None
    assert post(client, TRANSCRIPTION, "create_task", body).json() == first
    assert len(runner.calls) == 1
    reopened = TaskStore(runtime.config.data_dir / "tasks.sqlite3")
    assert reopened.get_for_principal(first["job_id"], CN).status == "submission_unknown"


def test_training_upload_submit_and_resource_ownership(service):
    client, runtime, runner = service
    job = post(client, VOICE, "create_training", {"request_id": "train", "name": "test", "sex": 2}).json()["job_id"]
    assert post(client, VOICE, "submit_training", {"request_id": "too-early", "job_id": job}).status_code == 409
    upload = {"request_id": "sample", "job_id": job, "audio_url": "https://example.test/voice.wav"}
    assert post(client, VOICE, "upload_sample", upload).json()["result"]["stage"] == "sample_uploaded"
    assert [c[1] for c in runner.calls] == ["create_training", "upload_sample"]
    post(client, VOICE, "upload_sample", upload)
    assert len(runner.calls) == 2
    submit = {"request_id": "submit", "job_id": job}
    assert post(client, VOICE, "submit_training", submit).json()["status"] == "running"
    post(client, VOICE, "submit_training", submit)
    assert len(runner.calls) == 3
    assert post(client, VOICE, "submit_training", {**submit, "request_id": "different"}).status_code == 409
    age(runtime, job)
    result = client.get(path(VOICE, "get_training"), params={"job_id": job}, headers=HEADERS).json()
    assert result["result"]["res_id"] == "owned-resource"
    assert runtime.tasks.owns_resource(CN, "owned-resource")
    assert not runtime.tasks.owns_resource(GLOBAL, "owned-resource")
    denied = client.post(path(VOICE, "synthesize"), json={"res_id": "owned-resource", "text": "hello"}, headers={"X-API-Key": OTHER_KEY})
    assert denied.status_code == 404


def test_local_job_worker_completes_and_clears_private_input(service):
    client, runtime, runner = service
    skill = "iflytek-contract-intelligence-review"
    result = post(client, skill, "review", {"request_id": "contract", "file_url": "https://example.test/private.txt"}).json()
    job = result["job_id"]
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = client.get(path(skill, "get_review"), params={"job_id": job}, headers=HEADERS).json()
        if result["status"] == "succeeded":
            break
        time.sleep(0.03)
    assert result["status"] == "succeeded"
    assert result["result"]["review"]["final_summary"] == "test finding"
    assert runtime.tasks.get_for_principal(job, CN).payload_json is None
    assert sum(action == "review" for _, action, _ in runner.calls) == 1


def test_restart_preserves_queued_local_input_and_upstream_mapping(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    local = store.create_or_reuse(CN, "animated-sketch-diagram", "render_html_to_gif", request_id="queued", payload={"html": "private"}, persist_payload=True)
    remote = store.create_or_reuse(CN, TRANSCRIPTION, "create_task", request_id="remote", payload={})
    store.acquire(remote.record.task_id, "owner")
    store.save(remote.record.task_id, "owner", status="running", upstream_id="remote-id")
    running = store.claim_next("old-worker", local_only=True)
    assert running.payload_json == '{"html": "private"}'
    queued = store.create_or_reuse(CN, "animated-sketch-diagram", "render_html_to_gif",
                                   request_id="not-started", payload={"html": "queued"}, persist_payload=True)
    reopened = TaskStore(tmp_path / "tasks.sqlite3")
    assert reopened.recover_after_restart() == 1
    assert reopened.get_for_principal(local.record.task_id, CN).status == "failed"
    assert reopened.get_for_principal(local.record.task_id, CN).error_code == "TIMEOUT"
    assert reopened.get_for_principal(local.record.task_id, CN).payload_json is None
    assert reopened.get_for_principal(remote.record.task_id, CN).upstream_id == "remote-id"
    assert reopened.get_for_principal(queued.record.task_id, CN).status == "queued"
    assert reopened.get_for_principal(queued.record.task_id, CN).payload_json is not None


def test_idle_maintenance_is_throttled_without_delaying_queue_polls(tmp_path, monkeypatch):
    from app import runtime as runtime_module
    runtime = Runtime(RuntimeConfig(tmp_path, "https://files.example.test"), runner=FakeRunner())
    clock = SimpleNamespace(now=0.0)
    events = {"expire": [], "cleanup": [], "poll": []}
    monkeypatch.setattr(runtime_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    monkeypatch.setattr(runtime.tasks, "expire", lambda: events["expire"].append(clock.now))
    monkeypatch.setattr(runtime.artifacts, "cleanup", lambda: events["cleanup"].append(clock.now))
    def claim(*args, **kwargs):
        events["poll"].append(clock.now)
        return None
    monkeypatch.setattr(runtime.tasks, "claim_next", claim)
    async def sleep(seconds):
        clock.now += seconds
        if clock.now > 60:
            raise asyncio.CancelledError()
    monkeypatch.setattr(runtime_module, "asyncio", SimpleNamespace(sleep=sleep))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime._work())
    assert events["expire"] == events["cleanup"] == [0, 30, 60]
    assert len(events["poll"]) == 241


def test_expired_lease_cannot_write_results(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    job = store.create_or_reuse(CN, TRANSCRIPTION, "create_task", request_id="one", payload={}).record.task_id
    store.acquire(job, "worker")
    with store._connect() as db:
        db.execute("UPDATE tasks SET lease_until = 0 WHERE task_id = ?", (job,))
    with pytest.raises(TaskStateError):
        store.save(job, "worker", status="succeeded", result={})
    assert store.expire() == 1
    assert store.get_for_principal(job, CN).status == "submission_unknown"


def test_second_coordinator_cannot_recover_live_work(service):
    _, runtime, _ = service
    other = Runtime(runtime.config, runner=FakeRunner())
    with pytest.raises(RuntimeError, match="one Coze coordinator"):
        asyncio.run(other.start())


def test_artifact_capability_expiry_download_and_safe_headers(service):
    client, runtime, _ = service
    artifact = runtime.artifacts.put_bytes(b"RIFFtest", "audio/wav")
    response = client.get(f"/v1/artifacts/{artifact.artifact_id}/input.wav")
    assert response.content == b"RIFFtest"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/v1/artifacts/{artifact.artifact_id}/input.mp4").status_code == 404
    runtime.artifacts.cleanup(now=time.time() + 4000)
    assert client.get(f"/v1/artifacts/{artifact.artifact_id}").status_code == 404


def test_real_isolated_runner_lists_voices_and_rejects_missing_credentials(tmp_path):
    runner = SkillRunner({})
    result = asyncio.run(runner.call("iflytek-hyper-tts", "list_voices", {}))
    assert result["all_voices"] and result["free_voices"]
    with pytest.raises(ServiceError) as error:
        asyncio.run(runner.call("iflytek-translate", "translate", {"text": "hello", "from_lang": "en", "to_lang": "cn"}))
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_unconfigured_runtime_responds_before_creating_a_task(tmp_path):
    runtime = Runtime(RuntimeConfig(tmp_path))
    with TestClient(create_app(SETTINGS, runtime=runtime)) as client:
        response = post(client, TRANSCRIPTION, "create_task", {"request_id": "test", "audio_url": "https://example.test/a.mp3"})
        assert response.status_code == 503
        assert runtime.tasks.claim_next("worker") is None
        response = post(client, "animated-sketch-diagram", "render_html_to_gif", {"request_id": "render", "html": "<div>x</div>"})
        assert response.status_code == 503


@pytest.mark.parametrize("body", [{"text": "x", "from_lang": "en", "api_key": "private"}, {"text": "字" * 1366}, {"text": ""}])
def test_invalid_inputs_never_reach_runner(service, body):
    client, _, runner = service
    assert post(client, "iflytek-translate", "translate", body).status_code == 422
    assert not runner.calls


def test_request_body_limit_is_checked_after_authentication(service):
    client, _, runner = service
    response = client.post(path("iflytek-translate", "translate"), content="x" * (2 * 1024 * 1024 + 1), headers=HEADERS)
    assert response.status_code == 422
    assert not runner.calls


def test_concurrent_retries_cannot_duplicate_paid_submissions(tmp_path):
    class SlowRunner(FakeRunner):
        async def call(self, *args, **kwargs):
            await asyncio.sleep(0.05)
            return await super().call(*args, **kwargs)
    runner = SlowRunner()
    runtime = Runtime(RuntimeConfig(tmp_path), runner=runner)
    async def calls():
        body = {"request_id": "concurrent", "audio_url": "https://example.test/a.mp3"}
        return await asyncio.gather(*(runtime.execute(CN, TRANSCRIPTION, "create_task", body) for _ in range(2)))
    results = asyncio.run(calls())
    assert results[0]["job_id"] == results[1]["job_id"]
    assert len(runner.calls) == 1


def test_cancelled_submission_releases_lease_but_stays_uncertain(tmp_path):
    class CancelledRunner(FakeRunner):
        async def call(self, *args, **kwargs):
            raise asyncio.CancelledError()
    runtime = Runtime(RuntimeConfig(tmp_path), runner=CancelledRunner())
    body = {"request_id": "cancel", "audio_url": "https://example.test/a.mp3"}
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.execute(CN, TRANSCRIPTION, "create_task", body))
    record = runtime.tasks.create_or_reuse(CN, TRANSCRIPTION, "create_task", request_id="cancel", payload=body).record
    assert record.status == "submission_unknown" and record.lease_owner is None


def test_local_queue_limit_keeps_existing_idempotency_keys_usable(tmp_path):
    from app.tasks import TaskQueueFull
    store = TaskStore(tmp_path / "tasks.sqlite3")
    for i in range(32):
        store.create_or_reuse(CN, "animated-sketch-diagram", "render_html_to_gif", request_id=str(i), payload={}, persist_payload=True)
    with pytest.raises(TaskQueueFull):
        store.create_or_reuse(CN, "animated-sketch-diagram", "render_html_to_gif", request_id="overflow", payload={}, persist_payload=True)
    assert store.create_or_reuse(CN, "animated-sketch-diagram", "render_html_to_gif", request_id="0", payload={}, persist_payload=True).reused


def test_timeout_kills_real_child_without_leaving_a_running_call():
    started = time.monotonic()
    with pytest.raises(ServiceError) as error:
        asyncio.run(SkillRunner({}).call("iflytek-hyper-tts", "list_voices", {}, timeout=0.001))
    assert error.value.code == ErrorCode.TIMEOUT
    assert time.monotonic() - started < 5


def test_child_environment_excludes_platform_and_unrelated_credentials(monkeypatch):
    original = asyncio.create_subprocess_exec
    environments = []
    async def spawn(*args, **kwargs):
        environments.append(kwargs["env"])
        return await original(*args, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setenv("IFLY_API_KEY", "ambient-private-value")
    runner = SkillRunner({"IFLY_API_KEY": "atomic-private", "IFLY_CONTRACT_API_KEY": "contract-private",
                          "COZE_CN_API_TOKEN": "platform-private"})
    asyncio.run(runner.call("iflytek-hyper-tts", "list_voices", {}))
    assert all(not key.startswith(("IFLY_", "COZE_CN_")) for key in environments[0])
