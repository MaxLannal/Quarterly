"""Raw page bytes in object storage (MinIO in Compose) plus one `source_snapshot` row each.

`MinioStore` speaks the S3 API with AWS Signature V4 using only the standard library (no new
dependency). It only ever talks to our own MinIO, never to a University site. Tests use
`MemoryStore`."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

import api.db.models as m
import sqlalchemy as sa
from sqlalchemy.orm import Session


class SnapshotStore(Protocol):
    def put(self, key: str, body: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


@dataclass
class MemoryStore:
    objects: dict[str, bytes] = field(default_factory=dict)

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = body

    def get(self, key: str) -> bytes:
        return self.objects[key]


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sigv4_headers(
    *,
    method: str,
    host: str,
    path: str,
    body: bytes,
    access_key: str,
    secret_key: str,
    now: dt.datetime,
    region: str = "us-east-1",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Headers for one signed S3 request (AWS Signature Version 4, no query string)."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    headers.update({k.lower(): v for k, v in (extra or {}).items()})
    signed = ";".join(sorted(headers))
    canonical = "\n".join(
        [
            method,
            urllib.parse.quote(path),
            "",
            "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers)),
            signed,
            payload_hash,
        ]
    )
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    k = _sign(f"AWS4{secret_key}".encode(), day)
    for part in (region, "s3", "aws4_request"):
        k = _sign(k, part)
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )
    return headers


@dataclass
class MinioStore:
    endpoint: str  # host:port of our own MinIO
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False

    def _request(self, method: str, key: str, body: bytes = b"", ctype: str = "") -> bytes:
        path = f"/{self.bucket}/{key}"
        extra = {"content-type": ctype} if ctype else None
        headers = sigv4_headers(
            method=method,
            host=self.endpoint,
            path=path,
            body=body,
            access_key=self.access_key,
            secret_key=self.secret_key,
            now=dt.datetime.now(dt.UTC),
            extra=extra,
        )
        scheme = "https" if self.secure else "http"
        url = f"{scheme}://{self.endpoint}{urllib.parse.quote(path)}"
        req = urllib.request.Request(url, data=body or None, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data: bytes = resp.read()
        return data

    def put(self, key: str, body: bytes, content_type: str) -> None:  # pragma: no cover
        self._request("PUT", key, body, content_type)

    def get(self, key: str) -> bytes:  # pragma: no cover - needs a running MinIO
        return self._request("GET", key)


def minio_store_from_settings() -> MinioStore:  # pragma: no cover - wiring
    from api.config import get_settings

    s = get_settings()
    return MinioStore(
        endpoint=s.minio_endpoint,
        access_key=s.minio_root_user,
        secret_key=s.minio_root_password.get_secret_value(),
        bucket=s.minio_bucket,
    )


def record_snapshot(
    db: Session,
    store: SnapshotStore,
    *,
    url: str,
    body: bytes,
    fetched_at: dt.datetime,
    content_type: str = "text/html; charset=utf-8",
    prefix: str = "class-search",
) -> m.SourceSnapshot:
    """Store the bytes and add a `source_snapshot` row. The same URL with the same bytes
    reuses its existing row. The caller commits."""
    sha = hashlib.sha256(body).hexdigest()
    existing = db.scalar(
        sa.select(m.SourceSnapshot)
        .where(m.SourceSnapshot.url == url, m.SourceSnapshot.sha256 == sha)
        .order_by(m.SourceSnapshot.id)
        .limit(1)
    )
    if existing is not None:
        return existing
    key = f"{prefix}/{sha[:2]}/{sha}.html"
    store.put(key, body, content_type)
    row = m.SourceSnapshot(
        url=url, fetched_at=fetched_at, sha256=sha, storage_key=key, content_type=content_type
    )
    db.add(row)
    db.flush()
    return row


def read_snapshot(
    db: Session, store: SnapshotStore, snapshot_id: int
) -> tuple[m.SourceSnapshot, str]:
    row = db.get(m.SourceSnapshot, snapshot_id)
    if row is None:
        raise LookupError(f"no source_snapshot {snapshot_id}")
    body = store.get(row.storage_key)
    if hashlib.sha256(body).hexdigest() != row.sha256:
        raise ValueError(f"snapshot {snapshot_id}: stored bytes do not match their sha256")
    return row, body.decode("utf-8", errors="replace")
