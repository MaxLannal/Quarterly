"""Snapshots: every fetched response, kept byte for byte.

The raw bytes go to object storage (MinIO in Docker, through its S3 API) under a
content-addressed key (`catalog/<sha256>`); a `source_snapshot` row records the URL, the
time, the sha256, the key and the content type (SPEC "Provenance and review"). Rule-tree
quotes point back at a snapshot id, and the verbatim-quote check reads the stored text.

`SnapshotArchive` pairs a byte store with a row log. Tests and the pilot use the in-memory
versions; the worker uses `MinioStore` and `DbSnapshotLog`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import itertools
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Snapshot:
    id: str
    url: str
    fetched_at: dt.datetime
    sha256: str
    storage_key: str
    content_type: str | None
    status: int
    body: bytes = field(repr=False)

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def storage_key_for(sha256: str) -> str:
    return f"catalog/{sha256[:2]}/{sha256}"


class SnapshotStore(Protocol):
    def put(self, key: str, body: bytes, content_type: str | None) -> None: ...

    def get(self, key: str) -> bytes: ...


class SnapshotLog(Protocol):
    def record(
        self,
        *,
        url: str,
        fetched_at: dt.datetime,
        sha256: str,
        storage_key: str,
        content_type: str | None,
    ) -> str:
        """Write one `source_snapshot` row; return its id."""
        ...


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, body: bytes, content_type: str | None) -> None:
        self.objects[key] = body

    def get(self, key: str) -> bytes:
        return self.objects[key]


class MemoryLog:
    """Rows in memory, ids `snap-1`, `snap-2`, ..."""

    def __init__(self, prefix: str = "snap") -> None:
        self.rows: dict[str, dict[str, object]] = {}
        self._ids = itertools.count(1)
        self.prefix = prefix

    def record(
        self,
        *,
        url: str,
        fetched_at: dt.datetime,
        sha256: str,
        storage_key: str,
        content_type: str | None,
    ) -> str:
        sid = f"{self.prefix}-{next(self._ids)}"
        self.rows[sid] = {
            "url": url,
            "fetched_at": fetched_at,
            "sha256": sha256,
            "storage_key": storage_key,
            "content_type": content_type,
        }
        return sid


class SnapshotArchive:
    """Saves responses (bytes to the store, a row to the log) and keeps them for reading."""

    def __init__(
        self,
        store: SnapshotStore,
        log: SnapshotLog,
        *,
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    ) -> None:
        self.store = store
        self.log = log
        self.now = now
        self.by_id: dict[str, Snapshot] = {}

    def save(self, url: str, status: int, body: bytes, content_type: str | None) -> Snapshot:
        digest = sha256_hex(body)
        key = storage_key_for(digest)
        self.store.put(key, body, content_type)
        fetched_at = self.now()
        sid = self.log.record(
            url=url,
            fetched_at=fetched_at,
            sha256=digest,
            storage_key=key,
            content_type=content_type,
        )
        snap = Snapshot(
            id=sid,
            url=url,
            fetched_at=fetched_at,
            sha256=digest,
            storage_key=key,
            content_type=content_type,
            status=status,
            body=body,
        )
        self.by_id[sid] = snap
        return snap

    def get(self, snapshot_id: str) -> Snapshot:
        return self.by_id[snapshot_id]


def memory_archive(prefix: str = "snap") -> SnapshotArchive:
    return SnapshotArchive(MemoryStore(), MemoryLog(prefix))


# ------------------------------------------------------------------------ MinIO (S3 API)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sigv4_authorization(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload_sha256: str,
    access_key: str,
    secret_key: str,
    region: str,
    service: str = "s3",
    amz_date: str,
) -> str:
    """AWS Signature Version 4 `Authorization` header value. `headers` must already hold
    `host`, `x-amz-date` and `x-amz-content-sha256`; all of them are signed."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path or "/", safe="/-_.~")
    query = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in sorted(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    )
    canon = {k.lower(): " ".join(v.strip().split()) for k, v in headers.items()}
    signed = ";".join(sorted(canon))
    canonical_headers = "".join(f"{k}:{canon[k]}\n" for k in sorted(canon))
    canonical_request = "\n".join([method, path, query, canonical_headers, signed, payload_sha256])
    day = amz_date[:8]
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    key = _hmac(("AWS4" + secret_key).encode(), day)
    for part in (region, service, "aws4_request"):
        key = _hmac(key, part)
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )


class StorageError(RuntimeError):
    pass


class MinioStore:
    """Path-style S3 requests to MinIO, signed with SigV4 (no extra dependency)."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        region: str = "us-east-1",
        client: httpx.Client | None = None,
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    ) -> None:
        self.base = f"{'https' if secure else 'http'}://{endpoint}"
        self.host = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self.client = client or httpx.Client(timeout=30.0)
        self.now = now
        self._bucket_ready = False

    def _request(
        self, method: str, path: str, body: bytes = b"", extra: dict[str, str] | None = None
    ) -> httpx.Response:
        url = self.base + path
        digest = hashlib.sha256(body).hexdigest()
        amz_date = self.now().strftime("%Y%m%dT%H%M%SZ")
        headers = {
            "host": self.host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": digest,
            **(extra or {}),
        }
        headers["authorization"] = sigv4_authorization(
            method=method,
            url=url,
            headers=headers,
            payload_sha256=digest,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            amz_date=amz_date,
        )
        return self.client.request(method, url, content=body, headers=headers)

    def ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        resp = self._request("PUT", f"/{self.bucket}")
        if resp.status_code not in (200, 409):  # 409: it exists already
            raise StorageError(f"could not create bucket {self.bucket}: {resp.status_code}")
        self._bucket_ready = True

    def put(self, key: str, body: bytes, content_type: str | None) -> None:
        self.ensure_bucket()
        extra = {"content-type": content_type} if content_type else {}
        resp = self._request("PUT", f"/{self.bucket}/{key}", body, extra)
        if resp.status_code != 200:
            raise StorageError(f"could not store {key}: {resp.status_code}")

    def get(self, key: str) -> bytes:
        resp = self._request("GET", f"/{self.bucket}/{key}")
        if resp.status_code != 200:
            raise StorageError(f"could not read {key}: {resp.status_code}")
        return resp.content
