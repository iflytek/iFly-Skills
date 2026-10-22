"""Tests for durable task ownership, idempotency and restart handling."""

from contextlib import closing, contextmanager
import sqlite3

import pytest

from app.config import Principal
from app.tasks import TaskConflict, TaskStateError, TaskStore, request_fingerprint


SKILL = "animated-sketch-diagram"
ACTION = "render_html_to_gif"
REMOTE_SKILL = "iflytek-speed-transcription"
CN = Principal("cn", "cn-space", frozenset({SKILL, REMOTE_SKILL}))
GLOBAL = Principal("global", "global-space", frozenset({SKILL, REMOTE_SKILL}))


def test_idempotency_reuses_identical_requests_and_conflicts_on_changed_input(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    first = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-1", payload={"html": "hello"}, persist_payload=True)
    second = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-1", payload={"html": "hello"}, persist_payload=True)
    assert first.reused is False
    assert second.reused is True
    assert second.record.task_id == first.record.task_id
    with pytest.raises(TaskConflict):
        store.create_or_reuse(CN, SKILL, ACTION, request_id="req-1", payload={"html": "different"}, persist_payload=True)


def test_task_records_survive_reopening_and_are_scoped_to_site_and_workspace(tmp_path):
    database = tmp_path / "nested" / "tasks.sqlite3"
    first_store = TaskStore(database)
    created = first_store.create_or_reuse(CN, REMOTE_SKILL, "create_task", request_id="req-2", payload={})
    first_store.acquire(created.record.task_id, "submitter")
    first_store.save(created.record.task_id, "submitter", status="running", upstream_id="private-upstream-id")
    reopened = TaskStore(database)
    assert reopened.get_for_principal(created.record.task_id, CN).task_id == created.record.task_id
    assert reopened.get_for_principal(created.record.task_id, CN).upstream_id == "private-upstream-id"
    assert reopened.get_for_principal(created.record.task_id, GLOBAL) is None
    assert "cn-space" not in repr(created.record)


def test_claim_save_and_worker_ownership_are_enforced(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    created = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-3", payload={"html": "hello"}, persist_payload=True)
    claimed = store.claim_next("worker-a", lease_seconds=60)
    assert claimed.task_id == created.record.task_id
    with pytest.raises(TaskStateError):
        store.save(claimed.task_id, "worker-b", status="succeeded", result={"frames": 8})
    completed = store.save(claimed.task_id, "worker-a", status="succeeded", result={"frames": 8})
    assert completed.status == "succeeded"
    assert completed.result_json == '{"frames": 8}'
    assert completed.payload_json is None and completed.lease_owner is None
    assert store.claim_next("worker-a") is None


def test_expired_and_abandoned_work_is_not_automatically_resubmitted(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    expired = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-4", payload={}, deadline_at=90, persist_payload=True)
    assert store.claim_next("worker-a", now=100) is None
    assert store.get_for_principal(expired.record.task_id, CN).status == "failed"

    uncertain = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-5", payload={}, deadline_at=200, persist_payload=True)
    claimed = store.claim_next("worker-a", now=100, lease_seconds=5)
    assert claimed.task_id == uncertain.record.task_id
    assert store.recover_after_restart(now=106) == 1
    record = store.get_for_principal(uncertain.record.task_id, CN)
    assert record.status == "failed"
    assert record.error_code == "TIMEOUT"
    assert store.claim_next("worker-a", now=107) is None


def test_expire_marks_running_and_queued_local_work_timed_out(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    running = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-7", payload={}, deadline_at=90, persist_payload=True)
    queued = store.create_or_reuse(CN, SKILL, ACTION, request_id="req-6", payload={}, deadline_at=90, persist_payload=True)
    claimed = store.claim_next("worker-a", now=80, lease_seconds=100)
    assert claimed.task_id == running.record.task_id
    assert store.expire(now=100) == 2
    assert store.get_for_principal(queued.record.task_id, CN).status == "failed"
    assert store.get_for_principal(running.record.task_id, CN).status == "failed"


@pytest.mark.parametrize("expiry", ["lease", "deadline"])
def test_local_work_is_failed_after_restart_or_lease_expiry(tmp_path, expiry):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    local_principal = Principal("cn", "cn-space", frozenset({"animated-sketch-diagram"}))
    local = store.create_or_reuse(local_principal, "animated-sketch-diagram", "render_html_to_gif",
                                  request_id="local", payload={"html": "x"}, persist_payload=True)
    store.acquire(local.record.task_id, "worker")
    assert store.recover_after_restart(now=100) == 1
    record = store.get_for_principal(local.record.task_id, local_principal)
    assert record.status == "failed" and record.error_code == "TIMEOUT"

    queued = store.create_or_reuse(local_principal, "animated-sketch-diagram", "render_html_to_gif",
                                   request_id="queued-local", payload={"html": "x"},
                                   persist_payload=True, deadline_at=90 if expiry == "deadline" else 200)
    claimed = store.claim_next("worker", now=80, lease_seconds=10 if expiry == "lease" else 100)
    assert claimed.task_id == queued.record.task_id
    assert store.expire(now=100) == 1
    record = store.get_for_principal(queued.record.task_id, local_principal)
    assert record.status == "failed" and record.error_code == "TIMEOUT"
    assert record.payload_json is None and record.lease_owner is None


def test_idle_queue_poll_does_not_compete_with_database_writer(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    original_connect = store._connect
    @contextmanager
    def no_wait_connect():
        with original_connect() as connection:
            connection.execute("PRAGMA busy_timeout=0")
            yield connection
    monkeypatch.setattr(store, "_connect", no_wait_connect)
    with closing(sqlite3.connect(store.database)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        assert store.claim_next("worker") is None


def test_queue_does_not_claim_upstream_submissions_or_missing_local_input(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    remote = store.create_or_reuse(CN, REMOTE_SKILL, "create_task", request_id="remote", payload={}, persist_payload=True)
    missing = store.create_or_reuse(CN, SKILL, ACTION, request_id="missing", payload={})
    local = store.create_or_reuse(CN, SKILL, ACTION, request_id="local", payload={"html": "queued"}, persist_payload=True)
    assert store.claim_next("worker").task_id == local.record.task_id
    assert store.claim_next("worker") is None
    assert store.get_for_principal(remote.record.task_id, CN).status == "queued"
    assert store.get_for_principal(missing.record.task_id, CN).status == "queued"


def test_fingerprints_are_stable_and_reject_non_json_values():
    assert request_fingerprint({"b": 2, "a": 1}) == request_fingerprint({"a": 1, "b": 2})
    with pytest.raises(ValueError):
        request_fingerprint({"value": float("nan")})
