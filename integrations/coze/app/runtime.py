"""Single-instance task coordinator; upstream jobs are queried, never resubmitted."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from .config import RUNTIME_KEYS, read_config
from .errors import ErrorCode, ServiceError
from .files import ArtifactStore
from .limits import ConcurrencyGate, ConcurrencyLimitError, SlidingWindowRateLimiter
from .runner import SkillRunner
from .tasks import TaskConflict, TaskQueueFull, TaskStateError, TaskStore


LOCAL = {"review", "render_html_to_gif"}
CREATES = {"create_task", "create_pdf_task", "create_training"} | LOCAL
MUTATIONS = {"upload_sample", "submit_training", "confirm_transcript"}
QUERIES = {"get_task", "get_pdf_task", "get_training", "get_review", "get_render"}
FINISHED = {"succeeded", "partially_succeeded", "failed"}
REJECTED = {ErrorCode.INVALID_REQUEST, ErrorCode.DEPENDENCY_UNAVAILABLE,
            ErrorCode.UPSTREAM_PERMISSION_DENIED, ErrorCode.UPSTREAM_QUOTA_EXCEEDED}


@dataclass(frozen=True)
class RuntimeConfig:
    data_dir: Path
    artifact_base_url: str = ""
    environment: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls):
        values = read_config(Path(os.environ["COZE_ENV_FILE"])) if os.environ.get("COZE_ENV_FILE") else {}
        values.update({key: os.environ[key] for key in RUNTIME_KEYS if key in os.environ})
        root = Path(values.get("COZE_DATA_DIR") or Path(__file__).resolve().parents[1] / "output" / "runtime").resolve()
        environment = {key: values[key] for key in RUNTIME_KEYS if values.get(key)}
        environment["COZE_DATA_DIR"] = str(root)
        return cls(root, values.get("COZE_ARTIFACT_BASE_URL", ""), environment)


class Runtime:
    def __init__(self, config: RuntimeConfig, *, runner=None):
        self.config = config
        self.runner = runner or SkillRunner(config.environment)
        self.tasks = TaskStore(config.data_dir / "tasks.sqlite3")
        self.artifacts = ArtifactStore(config.data_dir, config.artifact_base_url) if config.artifact_base_url else None
        self.rate = SlidingWindowRateLimiter(60, 60)
        self.gate = ConcurrencyGate(2)
        self.global_gate = ConcurrencyGate(4)
        self._lock_file = None
        self._worker = None

    async def start(self):
        # SQLite + local files require one coordinator, even with two enabled sites.
        path = self.config.data_dir / "coordinator.lock"
        self._lock_file = path.open("a+b")
        self._lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                if path.stat().st_size == 0:
                    self._lock_file.write(b"0")
                    self._lock_file.flush()
                self._lock_file.seek(0)
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock_file.close()
            self._lock_file = None
            raise RuntimeError("Only one Coze coordinator may use a data directory") from None
        self.tasks.recover_after_restart()
        self._worker = asyncio.create_task(self._work())

    async def close(self):
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        if self._lock_file:
            self._lock_file.close()
            self._lock_file = None

    @asynccontextmanager
    async def admission(self, principal):
        key = (principal.site, principal.workspace_id)
        if not self.rate.allow(key).allowed:
            raise ServiceError(ErrorCode.RATE_LIMITED)
        try:
            with self.global_gate.slot("all"), self.gate.slot(key):
                yield
        except ConcurrencyLimitError:
            raise ServiceError(ErrorCode.RATE_LIMITED) from None

    def preflight(self, skill, action):
        if not isinstance(self.runner, SkillRunner):
            return  # Injected test runner supplies its own dependency boundary.
        env = self.config.environment
        if skill == "animated-sketch-diagram":
            if not env.get("COZE_RENDER_IMAGE"):
                raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        elif action != "list_voices":
            prefix = "IFLY_CONTRACT" if skill == "iflytek-contract-intelligence-review" else "IFLY"
            fields = ("APP_ID", "API_KEY", "API_SECRET")
            if skill == "iflytek-video-translate":
                fields = ("API_KEY", "API_SECRET")
            elif skill == "iflytek-voiceclone-tts" and action != "synthesize":
                fields = ("APP_ID", "API_KEY")
            elif skill == "iflytek-pdf-image-ocr" and action != "recognize_image":
                fields = ("APP_ID", "API_SECRET")
            if any(not env.get(prefix + "_" + key, "").strip() for key in fields):
                raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        if (action in {"synthesize", "upload_sample", "review", "render_html_to_gif", "get_pdf_task"}
                or skill == "iflytek-video-translate") and self.artifacts is None:
            raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)

    def get(self, principal, skill, job_id):
        record = self.tasks.get_for_principal(job_id, principal)
        if record is None or record.skill_id != skill or record.action not in CREATES:
            raise ServiceError(ErrorCode.NOT_FOUND)
        return record

    @staticmethod
    def public(record):
        return {"job_id": record.task_id, "status": record.status,
                "result": json.loads(record.result_json) if record.result_json else None,
                "error_code": record.error_code, "poll_after_seconds": 5}

    async def execute(self, principal, skill, action, payload):
        async with self.admission(principal):
            try:
                if action in QUERIES:
                    return await self.query(principal, skill, action, payload["job_id"])
                if action in MUTATIONS:
                    return await self.mutate(principal, skill, action, payload)
                if action in CREATES:
                    return await self.create(principal, skill, action, payload)
                if skill == "iflytek-voiceclone-tts" and action == "synthesize":
                    if not self.tasks.owns_resource(principal, payload["res_id"]):
                        raise ServiceError(ErrorCode.NOT_FOUND)
                self.preflight(skill, action)
                return await self.runner.call(skill, action, payload)
            except (TaskConflict, TaskStateError):
                raise ServiceError(ErrorCode.CONFLICT) from None
            except TaskQueueFull:
                raise ServiceError(ErrorCode.RATE_LIMITED) from None

    def save_response(self, record, owner, response):
        from .tools import CONTRACTS
        try:
            CONTRACTS[record.skill_id][record.action][1].model_validate({
                "job_id": record.task_id, "status": response["status"],
                "result": response.get("result"), "error_code": response.get("error_code"),
            })
            if (record.action in CREATES - LOCAL and record.upstream_id is None
                    and not response.get("upstream_id")):
                raise ValueError("Missing upstream mapping")
        except (KeyError, TypeError, ValueError):
            raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR) from None
        return self.tasks.save(record.task_id, owner, status=response["status"], result=response.get("result"),
                               upstream_id=response.get("upstream_id"), error_code=response.get("error_code"))

    def save_failure(self, record, owner, error, *, local=False):
        code = error.code if isinstance(error, ServiceError) else ErrorCode.INTERNAL_ERROR
        uncertain = not local and code not in REJECTED
        return self.tasks.save(record.task_id, owner, status="submission_unknown" if uncertain else "failed",
                               result=json.loads(record.result_json) if record.result_json else None, error_code=str(code))

    async def create(self, principal, skill, action, payload):
        # Fingerprint input before downloading; a retry must reuse the same stable URL and parameters.
        self.preflight(skill, action)
        created = self.tasks.create_or_reuse(principal, skill, action, request_id=payload["request_id"],
                                            payload=payload, persist_payload=action in LOCAL,
                                            deadline_at=time.time() + 900 if action in LOCAL else None)
        record = created.record
        if created.reused or action in LOCAL:
            return self.public(record)
        owner = uuid4().hex
        record = self.tasks.acquire(record.task_id, owner)
        try:
            response = await self.runner.call(skill, action, payload)
            record = self.save_response(record, owner, response)
        except asyncio.CancelledError:
            self.save_failure(record, owner, ServiceError(ErrorCode.TIMEOUT))
            raise
        except Exception as exc:
            record = self.save_failure(record, owner, exc)
        return self.public(record)

    async def query(self, principal, skill, action, job_id):
        record = self.get(principal, skill, job_id)
        if (record.action in LOCAL or record.status in FINISHED or record.lease_owner
                or not record.upstream_id or time.time() - record.updated_at < 5):
            return self.public(record)
        # Training is queried only after explicit submission (or uncertain submission).
        result = json.loads(record.result_json or "{}")
        if skill == "iflytek-voiceclone-tts" and record.status != "submission_unknown" and result.get("stage") in {"created", "sample_uploaded"}:
            return self.public(record)
        self.preflight(skill, action)
        owner = uuid4().hex
        record = self.tasks.acquire(record.task_id, owner)
        try:
            response = await self.runner.call(skill, action, {"upstream_id": record.upstream_id})
            record = self.save_response(record, owner, response)
        except (Exception, asyncio.CancelledError):
            # Read failures do not erase a known submission or cause a second submission.
            self.tasks.save(record.task_id, owner, status=record.status, result=result, error_code=record.error_code)
            raise
        return self.public(record)

    async def mutate(self, principal, skill, action, payload):
        parent = self.get(principal, skill, payload["job_id"])
        self.preflight(skill, action)
        receipt = self.tasks.create_or_reuse(principal, skill, action, request_id=payload["request_id"], payload=payload)
        if receipt.reused:
            if receipt.record.status == "failed":
                raise ServiceError(ErrorCode(receipt.record.error_code))
            return self.public(parent)
        owner = uuid4().hex
        receipt_record = self.tasks.acquire(receipt.record.task_id, owner)
        try:
            parent = self.tasks.acquire(parent.task_id, owner)
        except Exception:
            self.tasks.save(receipt_record.task_id, owner, status="failed", error_code="CONFLICT")
            raise
        result = json.loads(parent.result_json or "{}")
        valid = (parent.status == "waiting_input" and parent.upstream_id and (
            action == "upload_sample" and result.get("stage") == "created"
            or action == "submit_training" and result.get("stage") == "sample_uploaded"
            or action == "confirm_transcript" and result.get("upstream_status") == "waiting_transcript_confirmation"))
        if not valid:
            self.tasks.save(parent.task_id, owner, status=parent.status, result=result, error_code=parent.error_code)
            self.tasks.save(receipt_record.task_id, owner, status="failed", error_code="CONFLICT")
            raise ServiceError(ErrorCode.CONFLICT)
        try:
            response = await self.runner.call(skill, action, {**payload, "upstream_id": parent.upstream_id})
            parent = self.save_response(parent, owner, response)
            self.tasks.save(receipt_record.task_id, owner, status="succeeded")
        except asyncio.CancelledError:
            self.save_failure(parent, owner, ServiceError(ErrorCode.TIMEOUT))
            self.save_failure(receipt_record, owner, ServiceError(ErrorCode.TIMEOUT))
            raise
        except Exception as exc:
            if isinstance(exc, ServiceError) and exc.code in REJECTED:
                self.tasks.save(parent.task_id, owner, status=parent.status, result=result, error_code=parent.error_code)
                self.save_failure(receipt_record, owner, exc)
                raise
            parent = self.save_failure(parent, owner, exc)
            self.save_failure(receipt_record, owner, exc)
        return self.public(parent)

    async def _work(self):
        while True:
            self.tasks.expire()
            if self.artifacts:
                self.artifacts.cleanup()
            owner = uuid4().hex
            record = self.tasks.claim_next(owner, lease_seconds=660, local_only=True)
            if record is None:
                await asyncio.sleep(0.25)
                continue
            try:
                payload = json.loads(record.payload_json)
                timeout = min(600, max(0.01, record.deadline_at - time.time())) if record.deadline_at else 600
                with self.global_gate.slot("all"), self.gate.slot((record.site, record.workspace_id)):
                    response = await self.runner.call(record.skill_id, record.action, payload, timeout=timeout)
                self.save_response(record, owner, response)
            except ConcurrencyLimitError:
                self.tasks.save(record.task_id, owner, status="queued")
                await asyncio.sleep(0.25)
            except asyncio.CancelledError:
                self.save_failure(record, owner, ServiceError(ErrorCode.TIMEOUT), local=True)
                raise
            except Exception as exc:
                self.save_failure(record, owner, exc, local=True)
