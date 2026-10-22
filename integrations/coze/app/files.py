"""Controlled input downloads and expiring artifact metadata."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import ipaddress
import http.client
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import secrets
import tempfile
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from .config import backend_url


class FileAccessError(ValueError):
    """Safe input or artifact error without a source URL or local path."""


@dataclass(frozen=True)
class FilePolicy:
    max_bytes: int = 32 * 1024 * 1024
    timeout_seconds: float = 30.0
    max_redirects: int = 3
    chunk_size: int = 64 * 1024
    allowed_mime_types: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.max_bytes <= 0 or self.timeout_seconds <= 0 or self.max_redirects < 0 or self.chunk_size <= 0:
            raise ValueError("File policy limits must be positive")


def _is_blocked_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    return not parsed.is_global


def _validate_remote_url(url: str, resolver: Callable[..., list] | None = None) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise FileAccessError("The file URL is invalid.") from None
    if parts.scheme.lower() != "https" or not host or parts.username or parts.password or parts.fragment:
        raise FileAccessError("The file URL must be an HTTPS URL without credentials or a fragment.")
    if port is not None and not 1 <= port <= 65535:
        raise FileAccessError("The file URL port is invalid.")
    host = host.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise FileAccessError("The file host is not publicly reachable.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if _is_blocked_address(str(address)):
            raise FileAccessError("The file host is not publicly reachable.")
    else:
        resolve = resolver or socket.getaddrinfo
        try:
            results = resolve(host, port or 443, type=socket.SOCK_STREAM)
        except (OSError, socket.gaierror):
            raise FileAccessError("The file host could not be resolved.") from None
        addresses = {str(item[4][0]) for item in results if item and item[4]}
        if not addresses or any(_is_blocked_address(item) for item in addresses):
            raise FileAccessError("The file host is not publicly reachable.")
    return url


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the checked address while retaining hostname/SNI verification."""

    def connect(self):
        addresses = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        if not addresses or any(_is_blocked_address(item[4][0]) for item in addresses):
            raise FileAccessError("The file host is not publicly reachable.")
        last_error = None
        for family, socktype, proto, _, address in addresses:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(self.timeout)
            try:
                sock.connect(address)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as exc:
                last_error = exc
                sock.close()
        raise OSError("The file host could not be reached.") from last_error


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context)


def _close_quietly(stream: object) -> None:
    close = getattr(stream, "close", None)
    if close is not None:
        try:
            close()
        except OSError:
            pass


@dataclass
class DownloadedFile:
    path: Path
    mime_type: str
    size_bytes: int
    source_url: str

    def cleanup(self) -> None:
        parent = self.path.parent
        try:
            self.path.unlink(missing_ok=True)
            if parent.name.startswith("coze-input-"):
                parent.rmdir()
        except OSError:
            pass

    def __enter__(self) -> "DownloadedFile":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


class FileDownloader:
    def __init__(self, policy: FilePolicy | None = None, *, temp_root: Path | None = None,
                 opener=None, resolver: Callable[..., list] | None = None):
        self.policy = policy or FilePolicy()
        self.temp_root = temp_root
        self.opener = opener or build_opener(ProxyHandler({}), _NoRedirect(), _PinnedHTTPSHandler())
        self.resolver = resolver

    def download(self, url: str) -> DownloadedFile:
        started = time.monotonic()
        current = _validate_remote_url(url, self.resolver)
        response = None
        for _ in range(self.policy.max_redirects + 1):
            request = Request(current, headers={"Accept": "*/*", "User-Agent": "ifly-skills-coze/1"})
            try:
                remaining = self.policy.timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise FileAccessError("The file download timed out.")
                response = self.opener.open(request, timeout=remaining)
            except HTTPError as exc:
                if 300 <= exc.code < 400:
                    location = exc.headers.get("Location") if exc.headers else None
                    _close_quietly(exc)
                    if not location:
                        raise FileAccessError("The file redirect has no destination.") from None
                    current = _validate_remote_url(urljoin(current, location), self.resolver)
                    continue
                _close_quietly(exc)
                raise FileAccessError("The file server returned an error.") from None
            except (OSError, URLError, TimeoutError):
                raise FileAccessError("The file could not be downloaded.") from None
            break
        else:
            raise FileAccessError("Too many file redirects.")

        directory = None
        try:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise FileAccessError("The file server returned an invalid status.")
            headers = getattr(response, "headers", None)
            mime_type = "application/octet-stream"
            if headers is not None:
                get_content_type = getattr(headers, "get_content_type", None)
                mime_type = get_content_type() if get_content_type else str(headers.get("Content-Type", mime_type)).split(";", 1)[0].strip().lower()
                content_length = headers.get("Content-Length")
                if content_length is not None:
                    try:
                        length = int(content_length)
                    except ValueError:
                        raise FileAccessError("The file size header is invalid.") from None
                    if length < 0 or length > self.policy.max_bytes:
                        raise FileAccessError("The file exceeds the configured size limit.")
            if self.policy.allowed_mime_types and mime_type not in self.policy.allowed_mime_types:
                raise FileAccessError("The file media type is not allowed.")
            directory = Path(tempfile.mkdtemp(prefix="coze-input-", dir=str(self.temp_root) if self.temp_root else None))
            target = directory / "input"
            total = 0
            with target.open("wb") as output:
                while True:
                    if time.monotonic() - started > self.policy.timeout_seconds:
                        raise FileAccessError("The file download timed out.")
                    chunk = response.read(min(self.policy.chunk_size, self.policy.max_bytes - total + 1))
                    if time.monotonic() - started > self.policy.timeout_seconds:
                        raise FileAccessError("The file download timed out.")
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.policy.max_bytes:
                        raise FileAccessError("The file exceeds the configured size limit.")
                    output.write(chunk)
            if total == 0:
                raise FileAccessError("The downloaded file is empty.")
            return DownloadedFile(target, mime_type, total, current)
        except FileAccessError:
            if directory is not None:
                shutil.rmtree(directory, ignore_errors=True)
            raise
        except (OSError, TimeoutError):
            if directory is not None:
                shutil.rmtree(directory, ignore_errors=True)
            raise FileAccessError("The file could not be saved safely.") from None
        finally:
            _close_quietly(response)


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    url: str
    mime_type: str
    size_bytes: int
    expires_at: str


_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


class ArtifactStore:
    """Persistent local artifact metadata with expiring opaque URLs."""

    def __init__(self, root: Path, base_url: str, *, default_ttl_seconds: int = 3600,
                 max_storage_bytes: int = 2 * 1024 * 1024 * 1024):
        self.root = root.resolve()
        self.base_url = backend_url(base_url)
        if default_ttl_seconds <= 0:
            raise ValueError("Artifact TTL must be positive")
        self.default_ttl_seconds = default_ttl_seconds
        if max_storage_bytes <= 0:
            raise ValueError("Artifact storage limit must be positive")
        self.max_storage_bytes = max_storage_bytes
        self.data_root = self.root / "artifacts"
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "artifacts.sqlite3"
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    relative_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    @staticmethod
    def _format_expiry(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")

    def put_file(self, source: Path, mime_type: str, *, ttl_seconds: int | None = None) -> Artifact:
        source = source.resolve()
        if not source.is_file():
            raise FileAccessError("The artifact source is not a regular file.")
        size = source.stat().st_size
        return self._put(source, mime_type, size, ttl_seconds)

    def put_bytes(self, data: bytes, mime_type: str, *, ttl_seconds: int | None = None) -> Artifact:
        if not isinstance(data, bytes) or not data:
            raise FileAccessError("The artifact content is empty.")
        temporary = self.data_root / ("." + secrets.token_hex(12) + ".tmp")
        temporary.write_bytes(data)
        try:
            return self._put(temporary, mime_type, len(data), ttl_seconds)
        finally:
            temporary.unlink(missing_ok=True)

    def _put(self, source: Path, mime_type: str, size: int, ttl_seconds: int | None) -> Artifact:
        if not re.fullmatch(r"[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+", mime_type) or not 0 < size <= 128 * 1024 * 1024:
            raise FileAccessError("The artifact metadata is invalid.")
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("Artifact TTL must be positive")
        artifact_id = secrets.token_urlsafe(24)
        destination = self.data_root / artifact_id
        temporary = self.data_root / ("." + artifact_id + ".tmp")
        try:
            # Stage large files without holding SQLite's writer lock.
            shutil.copyfile(source, temporary)
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                stored = connection.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM artifacts").fetchone()[0]
                if stored + size > self.max_storage_bytes:
                    raise FileAccessError("The artifact storage limit has been reached.")
                now = time.time()
                expires = now + ttl
                os.replace(temporary, destination)
                connection.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
                                   (artifact_id, destination.name, mime_type, size, expires, now))
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        return Artifact(artifact_id, f"{self.base_url}/v1/artifacts/{artifact_id}", mime_type, size,
                        self._format_expiry(expires))

    def resolve(self, artifact_id: str, *, now: float | None = None) -> tuple[Path, Artifact] | None:
        if not _ARTIFACT_ID.fullmatch(artifact_id):
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        if row is None or float(row["expires_at"]) <= (time.time() if now is None else now):
            return None
        path = (self.data_root / row["relative_path"]).resolve()
        if self.data_root not in path.parents or not path.is_file():
            return None
        return path, Artifact(row["artifact_id"], f"{self.base_url}/v1/artifacts/{row['artifact_id']}",
                             row["mime_type"], row["size_bytes"], self._format_expiry(row["expires_at"]))

    def cleanup(self, *, now: float | None = None) -> int:
        timestamp = time.time() if now is None else now
        with self._connect() as connection:
            rows = connection.execute("SELECT artifact_id, relative_path FROM artifacts WHERE expires_at <= ?", (timestamp,)).fetchall()
        removed = 0
        for row in rows:
            path = (self.data_root / row["relative_path"]).resolve()
            if self.data_root in path.parents:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    # Windows may still have a response stream open. Keep the expired
                    # metadata so the next cleanup can retry without exposing the URL.
                    continue
            with self._connect() as connection:
                connection.execute("DELETE FROM artifacts WHERE artifact_id = ? AND expires_at <= ?",
                                   (row["artifact_id"], timestamp))
            removed += 1
        return removed
