"""Tests for SSRF-safe downloads and persistent artifact expiry."""

from email.message import Message
from io import BytesIO
import socket
import time
from urllib.error import HTTPError

import pytest

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
    assert reopened.cleanup(now=now + 11) == 1
    assert reopened.resolve(artifact.artifact_id, now=now + 11) is None


def test_artifact_base_url_and_metadata_are_validated(tmp_path):
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path, "http://service.example.test")
    store = ArtifactStore(tmp_path, "https://service.example.test")
    with pytest.raises(FileAccessError):
        store.put_bytes(b"", "application/octet-stream")
