"""Persistent task records, scoped idempotency and restart-safe state changes."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from uuid import uuid4

from .catalog import Tool
from .config import Principal


TASK_STATUSES = frozenset({
    "queued", "running", "waiting_input", "succeeded", "partially_succeeded", "failed", "submission_unknown",
})
_REQUEST_ID = re.compile(r"^\S{1,256}$")


class TaskConflict(ValueError):
    """The same idempotency key was used with different input."""


class TaskStateError(ValueError):
    """A task cannot make the requested state transition."""


def request_fingerprint(payload: Any) -> str:
    """Hash a normalized request payload; callers must omit credentials and secrets."""
    try:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("The request payload cannot be fingerprinted safely.") from None
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    site: str
    workspace_id: str = field(repr=False)
    skill_id: str
    action: str
    request_id: str | None
    request_fingerprint: str
    status: str
    upstream_id: str | None
    result_json: str | None
    artifact_id: str | None
    error_code: str | None
    created_at: float
    updated_at: float
    deadline_at: float | None
    lease_owner: str | None
    lease_until: float | None
    attempts: int


@dataclass(frozen=True)
class TaskCreation:
    record: TaskRecord
    reused: bool


class TaskStore:
    """SQLite-backed records with authorization and no automatic resubmission."""

    def __init__(self, database: Path):
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    site TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    request_id TEXT,
                    request_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    upstream_id TEXT,
                    result_json TEXT,
                    artifact_id TEXT,
                    error_code TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    deadline_at REAL,
                    lease_owner TEXT,
                    lease_until REAL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    CHECK (status IN ('queued', 'running', 'waiting_input', 'succeeded', 'partially_succeeded', 'failed', 'submission_unknown'))
                )
            """)
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS task_idempotency ON tasks(site, workspace_id, skill_id, action, request_id) WHERE request_id IS NOT NULL")
            connection.execute("CREATE INDEX IF NOT EXISTS task_queue ON tasks(status, created_at)")

    @staticmethod
    def _validate_request_id(request_id: str | None) -> str | None:
        if request_id is None:
            return None
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            raise ValueError("request_id must be a non-empty identifier without whitespace")
        return request_id

    @staticmethod
    def _record(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(**dict(row))

    @staticmethod
    def _same_scope(record: TaskRecord, principal: Principal, skill_id: str | None = None) -> bool:
        return (record.site == principal.site and record.workspace_id == principal.workspace_id
                and (skill_id is None or record.skill_id == skill_id)
                and record.skill_id in principal.allowed_skills)

    def create_or_reuse(self, principal: Principal, skill_id: str, action: str, *,
                        request_id: str | None, payload: Any, deadline_at: float | None = None) -> TaskCreation:
        Tool(skill_id, action)
        if skill_id not in principal.allowed_skills:
            raise PermissionError("The service key is not authorized for this Skill.")
        request_id = self._validate_request_id(request_id)
        fingerprint = request_fingerprint(payload)
        now = time.time()
        task_id = uuid4().hex
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = None
            if request_id is not None:
                existing = connection.execute(
                    "SELECT * FROM tasks WHERE site = ? AND workspace_id = ? AND skill_id = ? AND action = ? AND request_id = ?",
                    (principal.site, principal.workspace_id, skill_id, action, request_id),
                ).fetchone()
            if existing is not None:
                record = self._record(existing)
                if record.request_fingerprint != fingerprint:
                    raise TaskConflict("The request_id was already used with different input.")
                return TaskCreation(record, True)
            connection.execute(
                """INSERT INTO tasks (task_id, site, workspace_id, skill_id, action, request_id, request_fingerprint,
                   status, created_at, updated_at, deadline_at, attempts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, 0)""",
                (task_id, principal.site, principal.workspace_id, skill_id, action, request_id, fingerprint,
                 now, now, deadline_at),
            )
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return TaskCreation(self._record(row), False)

    def get_for_principal(self, task_id: str, principal: Principal) -> TaskRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        record = self._record(row)
        return record if self._same_scope(record, principal) else None

    def claim_next(self, worker_id: str, *, now: float | None = None, lease_seconds: float = 60.0) -> TaskRecord | None:
        if not worker_id or not _REQUEST_ID.fullmatch(worker_id) or lease_seconds <= 0:
            raise ValueError("A valid worker ID and positive lease are required")
        timestamp = time.time() if now is None else now
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT * FROM tasks WHERE status = 'queued' ORDER BY created_at LIMIT 100").fetchall()
            for row in rows:
                if row["deadline_at"] is not None and row["deadline_at"] <= timestamp:
                    connection.execute("UPDATE tasks SET status = 'failed', error_code = 'TIMEOUT', updated_at = ? WHERE task_id = ? AND status = 'queued'",
                                       (timestamp, row["task_id"]))
                    continue
                changed = connection.execute(
                    """UPDATE tasks SET status = 'running', lease_owner = ?, lease_until = ?, attempts = attempts + 1, updated_at = ?
                       WHERE task_id = ? AND status = 'queued'""",
                    (worker_id, timestamp + lease_seconds, timestamp, row["task_id"]),
                ).rowcount
                if changed:
                    claimed = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (row["task_id"],)).fetchone()
                    return self._record(claimed)
        return None

    def renew_lease(self, task_id: str, worker_id: str, *, lease_seconds: float = 60.0,
                    now: float | None = None) -> TaskRecord:
        if not worker_id or lease_seconds <= 0:
            raise ValueError("A valid worker ID and positive lease are required")
        timestamp = time.time() if now is None else now
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE tasks SET lease_until = ?, updated_at = ? WHERE task_id = ? AND status = 'running' AND lease_owner = ? AND (lease_until IS NULL OR lease_until > ?)",
                (timestamp + lease_seconds, timestamp, task_id, worker_id, timestamp),
            ).rowcount
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not changed or row is None:
            raise TaskStateError("The task lease is no longer valid.")
        return self._record(row)

    def set_upstream_id(self, task_id: str, worker_id: str, upstream_id: str) -> TaskRecord:
        if not upstream_id or not isinstance(upstream_id, str):
            raise ValueError("A non-empty upstream ID is required")
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE tasks SET upstream_id = ?, updated_at = ? WHERE task_id = ? AND status = 'running' AND lease_owner = ?",
                (upstream_id, time.time(), task_id, worker_id),
            ).rowcount
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not changed or row is None:
            raise TaskStateError("The task is not owned by this worker.")
        return self._record(row)

    def complete(self, task_id: str, worker_id: str, *, result: Any = None, artifact_id: str | None = None,
                 status: str = "succeeded") -> TaskRecord:
        if status not in {"succeeded", "partially_succeeded", "waiting_input"}:
            raise ValueError("The completion status is invalid")
        result_json = None if result is None else json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._connect() as connection:
            now = time.time()
            changed = connection.execute(
                """UPDATE tasks SET status = ?, result_json = ?, artifact_id = ?, error_code = NULL,
                   lease_owner = NULL, lease_until = NULL, updated_at = ?
                   WHERE task_id = ? AND status = 'running' AND lease_owner = ?""",
                (status, result_json, artifact_id, now, task_id, worker_id),
            ).rowcount
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not changed or row is None:
            raise TaskStateError("The task is not owned by this worker.")
        return self._record(row)

    def fail(self, task_id: str, worker_id: str, error_code: str, *, uncertain_submission: bool = False) -> TaskRecord:
        if not error_code or any(char.isspace() for char in error_code):
            raise ValueError("A safe error code is required")
        status = "submission_unknown" if uncertain_submission else "failed"
        with self._connect() as connection:
            now = time.time()
            changed = connection.execute(
                "UPDATE tasks SET status = ?, error_code = ?, lease_owner = NULL, lease_until = NULL, updated_at = ? WHERE task_id = ? AND status = 'running' AND lease_owner = ?",
                (status, error_code, now, task_id, worker_id),
            ).rowcount
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not changed or row is None:
            raise TaskStateError("The task is not owned by this worker.")
        return self._record(row)

    def recover_after_restart(self, *, now: float | None = None) -> int:
        """Mark abandoned running work uncertain; never resubmit it automatically."""
        timestamp = time.time() if now is None else now
        with self._connect() as connection:
            changed = connection.execute(
                """UPDATE tasks SET status = 'submission_unknown', error_code = 'SUBMISSION_UNKNOWN',
                   lease_owner = NULL, lease_until = NULL, updated_at = ?
                   WHERE status = 'running'""",
                (timestamp,),
            ).rowcount
        return changed

    def expire(self, *, now: float | None = None) -> int:
        """Expire queued work and mark running work uncertain without retrying it."""
        timestamp = time.time() if now is None else now
        with self._connect() as connection:
            queued = connection.execute(
                "UPDATE tasks SET status = 'failed', error_code = 'TIMEOUT', updated_at = ? WHERE status = 'queued' AND deadline_at IS NOT NULL AND deadline_at <= ?",
                (timestamp, timestamp),
            ).rowcount
            running = connection.execute(
                """UPDATE tasks SET status = 'submission_unknown', error_code = 'SUBMISSION_UNKNOWN',
                   lease_owner = NULL, lease_until = NULL, updated_at = ?
                   WHERE status = 'running' AND deadline_at IS NOT NULL AND deadline_at <= ?""",
                (timestamp, timestamp),
            ).rowcount
        return queued + running
