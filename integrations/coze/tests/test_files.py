"""Tests for SSRF-safe downloads and persistent artifact expiry."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from email.message import Message
from io import BytesIO
import socket
import sqlite3
from threading import Barrier
import time
from urllib.error import HTTPError

import pytest


def test_connected_address_is_checked_and_pinned_with_original_tls_host(monkeypatch):
    import app.files as files
    events = []
    class Socket:
        def settimeout(self, value): pass
        def connect(self, address): events.append(("connect", address))
        def close(self): pass
    class Context:
        def wrap_socket(self, sock, server_hostname):
            events.append(("sni", server_hostname))
            return sock
    monkeypatch.setattr(files.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(files.socket, "socket", lambda *a: Socket())
    connection = files._PinnedHTTPSConnection("public.example.test", timeout=1)
    connection._context = Context()
    connection.connect()
    assert events == [("connect", ("93.184.216.34", 443)), ("sni", "public.example.test")]
    events.clear()
    monkeypatch.setattr(files.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(files.FileAccessError):
        connection.connect()
    assert events == []


def test_artifact_capacity_does_not_leave_partial_files(tmp_path):
    from app.files import ArtifactStore, FileAccessError
    store = ArtifactStore(tmp_path, "https://files.example.test", max_storage_bytes=4)
    store.put_bytes(b"1234", "text/plain")
    with pytest.raises(FileAccessError, match="storage limit"):
        store.put_bytes(b"5", "text/plain")
    assert len(list(store.data_root.iterdir())) == 1


def test_artifact_copy_leaves_database_available_to_other_writers(tmp_path, monkeypatch):
    import app.files as files
    store = ArtifactStore(tmp_path / "store", "https://files.example.test")
    source = tmp_path / "source.txt"
    source.write_bytes(b"data")
    original_copy = files.shutil.copyfile

    def copy_with_another_writer(source, destination):
        with closing(sqlite3.connect(store.db_path, timeout=0)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            return original_copy(source, destination)

    monkeypatch.setattr(files.shutil, "copyfile", copy_with_another_writer)
    artifact = store.put_file(source, "text/plain")
    assert store.resolve(artifact.artifact_id)[0].read_bytes() == b"data"


def test_concurrent_staged_artifacts_cannot_exceed_capacity(tmp_path, monkeypatch):
    import app.files as files
    stores = [ArtifactStore(tmp_path / "store", "https://files.example.test", max_storage_bytes=4)
              for _ in range(2)]
    source = tmp_path / "source.txt"
    source.write_bytes(b"data")
    staged = Barrier(2, timeout=5)
    original_copy = files.shutil.copyfile

    def concurrent_copy(source, destination):
        original_copy(source, destination)
        staged.wait()

    def put(store):
        try:
            return store.put_file(source, "text/plain")
        except FileAccessError as error:
            return error

    monkeypatch.setattr(files.shutil, "copyfile", concurrent_copy)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(put, store) for store in stores]
        results = [future.result(timeout=10) for future in futures]
    rejected = [result for result in results if isinstance(result, FileAccessError)]
    accepted = [result for result in results if not isinstance(result, FileAccessError)]
    assert len(rejected) == len(accepted) == 1
    assert "storage limit" in str(rejected[0])
    store = stores[0]
    with store._connect() as connection:
        assert connection.execute("SELECT SUM(size_bytes) FROM artifacts").fetchone()[0] == 4
    assert list(store.data_root.iterdir()) == [store.data_root / accepted[0].artifact_id]
    assert store.resolve(accepted[0].artifact_id)[0].read_bytes() == b"data"


@pytest.mark.parametrize("failure", ["copy", "insert"])
def test_artifact_write_failure_cleans_staged_and_published_files(tmp_path, monkeypatch, failure):
    import app.files as files
    store = ArtifactStore(tmp_path / "store", "https://files.example.test")
    source = tmp_path / "source.txt"
    source.write_bytes(b"data")
    if failure == "copy":
        def fail_copy(source, destination):
            destination.write_bytes(b"partial")
            raise OSError("copy failed")
        monkeypatch.setattr(files.shutil, "copyfile", fail_copy)
        error_type = OSError
    else:
        with store._connect() as connection:
            connection.execute("""
                CREATE TRIGGER fail_insert BEFORE INSERT ON artifacts
                BEGIN SELECT RAISE(ABORT, 'insert failed'); END
            """)
        error_type = sqlite3.IntegrityError
    with pytest.raises(error_type, match=f"{failure} failed"):
        store.put_file(source, "text/plain")
    assert source.read_bytes() == b"data"
    assert not list(store.data_root.iterdir())
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_cleanup_retries_files_still_open_on_windows(tmp_path, monkeypatch):
    from pathlib import Path
    from app.files import ArtifactStore
    store = ArtifactStore(tmp_path, "https://files.example.test")
    artifact = store.put_bytes(b"data", "text/plain")
    original = Path.unlink
    def busy(path, **kwargs):
        if path.name == artifact.artifact_id:
            raise PermissionError("open stream")
        return original(path, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", busy)
        assert store.cleanup(now=10**12) == 0
        assert store.resolve(artifact.artifact_id, now=10**12) is None
    assert store.cleanup(now=10**12) == 1

from app.files import ArtifactStore, FileAccessError, FileDownloader, FilePolicy


def public_resolver(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


class Response:
    status = 200

    def __init__(self, body, content_type="text/plain"):
        self._body = BytesIO(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(body))

    def read(self, size=-1):
        return self._body.read(size)

    def close(self):
        self._body.close()


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def open(self, request, timeout):
        self.urls.append(request.full_url)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_private_and_non_https_file_urls_are_rejected_before_network_access(tmp_path):
    opener = Opener([Response(b"should not be read")])
    downloader = FileDownloader(opener=opener, temp_root=tmp_path)
    with pytest.raises(FileAccessError):
        downloader.download("http://127.0.0.1/private")
    assert opener.urls == []


def test_download_follows_only_valid_https_redirects_and_cleans_temp_file(tmp_path):
    headers = Message()
    headers["Location"] = "https://files.example.test/final"
    redirect = HTTPError("https://files.example.test/start", 302, "redirect", headers, BytesIO())
    opener = Opener([redirect, Response(b"hello", "text/plain")])
    downloader = FileDownloader(opener=opener, temp_root=tmp_path, resolver=public_resolver)
    with downloader.download("https://files.example.test/start") as downloaded:
        assert downloaded.path.read_bytes() == b"hello"
        assert downloaded.size_bytes == 5
        assert downloaded.mime_type == "text/plain"
        assert downloaded.source_url.endswith("/final")
    assert not list(tmp_path.iterdir())


def test_download_size_limit_applies_even_without_a_content_length_header(tmp_path):
    response = Response(b"123456")
    del response.headers["Content-Length"]
    downloader = FileDownloader(policy=FilePolicy(max_bytes=5), temp_root=tmp_path,
                                 opener=Opener([response]), resolver=public_resolver)
    with pytest.raises(FileAccessError, match="size limit"):
        downloader.download("https://files.example.test/input")
    assert not list(tmp_path.iterdir())


def test_artifact_store_persists_opaque_urls_and_expires_them(tmp_path):
    store = ArtifactStore(tmp_path, "https://service.example.test", default_ttl_seconds=60)
    artifact = store.put_bytes(b"report", "application/json", ttl_seconds=10)
    assert artifact.url == f"https://service.example.test/v1/artifacts/{artifact.artifact_id}"
    now = time.time()
    resolved = store.resolve(artifact.artifact_id, now=now)
    assert resolved is not None
    path, metadata = resolved
    assert path.read_bytes() == b"report"
    assert metadata.mime_type == "application/json"
    reopened = ArtifactStore(tmp_path, "https://service.example.test")
    assert reopened.resolve(artifact.artifact_id, now=now) is not None
    assert reopened.resolve(artifact.artifact_id, now=now + 11) is None
    assert path.exists()  # Expiry denies access even before the cleanup worker runs.
    assert reopened.cleanup(now=now + 11) == 1
    assert reopened.resolve(artifact.artifact_id, now=now + 11) is None


def test_artifact_base_url_and_metadata_are_validated(tmp_path):
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path, "http://service.example.test")
    store = ArtifactStore(tmp_path, "https://service.example.test")
    with pytest.raises(FileAccessError):
        store.put_bytes(b"", "application/octet-stream")


@pytest.mark.parametrize("url", ["https://localhost", "https://files.example.local", "https://api.coze.cn",
    "https://127.0.0.1", "https://files.example:bad", "https://files.example:0",
    "https://files.example/v1/artifacts", "https://files.example/../proxy",
    "https://private-token@files.example", "https://files.example/?token=private-token"])
def test_artifact_service_address_rejects_invalid_hosts_ports_and_prefixes(tmp_path, url):
    with pytest.raises(ValueError) as error:
        ArtifactStore(tmp_path, url)
    assert "private-token" not in str(error.value)
    assert not list(tmp_path.iterdir())


def test_artifact_address_preserves_public_port_and_proxy_prefix(tmp_path):
    store = ArtifactStore(tmp_path, "https://files.example:8443/proxy/")
    artifact = store.put_bytes(b"report", "text/plain")
    assert artifact.url == f"https://files.example:8443/proxy/v1/artifacts/{artifact.artifact_id}"
    assert store.resolve(artifact.artifact_id)[1].url == artifact.url
