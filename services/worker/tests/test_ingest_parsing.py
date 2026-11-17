"""CourseLeaf parsing (code only), staged course rows and their diff, and the snapshot store."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import httpx
from worker.ingest import courseleaf
from worker.ingest.courses import course_batches, parse_courses
from worker.ingest.snapshots import (
    EMPTY_SHA256,
    MinioStore,
    Snapshot,
    memory_archive,
    sigv4_authorization,
)

FIX = Path(__file__).parent / "fixtures" / "catalog"


def page(rel: str, sid: str = "s1") -> Snapshot:
    body = (FIX / rel / "index.html").read_bytes()
    return Snapshot(
        id=sid,
        url=f"http://catalog.test/{rel}/",
        fetched_at=dt.datetime(2026, 8, 1, tzinfo=dt.UTC),
        sha256=hashlib.sha256(body).hexdigest(),
        storage_key="k",
        content_type="text/html",
        status=200,
        body=body,
    )


def test_page_text_is_the_visible_text_collapsed() -> None:
    text = courseleaf.page_text((FIX / "thecollege/fakescience/index.html").read_text())
    assert "must complete the introductory sequence: FSCI 10100 and FSCI 10200." in text
    assert "FSCI 10100 & FSCI 10200" in text  # entities decoded
    assert "tracking" not in text  # scripts are not text


def test_links_inside_a_container_are_absolute_and_deduplicated() -> None:
    html = (FIX / "azindex/index.html").read_text()
    found = courseleaf.links(html, "http://catalog.test/azindex/", within_id="textcontainer")
    urls = [u for u, _ in found]
    assert "http://catalog.test/thecollege/fakescience/" in urls  # fragment dropped
    assert "https://elsewhere.example/thecollege/other/" in urls
    assert courseleaf.links(html, "http://catalog.test/", within_id="missing") == []


def test_course_blocks_parse_every_field() -> None:
    blocks, problems = courseleaf.course_blocks(
        (FIX / "thecollege/fakescience/index.html").read_text()
    )
    by = {b.code: b for b in blocks}
    assert set(by) == {"FSCI 10100", "FSCI 10150", "FSCI 10200", "FSCI 20100"}
    intro = by["FSCI 10100"]
    assert intro.title == "Fake Science I" and intro.units == 100
    assert intro.title_line == "FSCI 10100. Fake Science I. 100 Units."
    assert intro.details["terms_offered"] == "Autumn Winter"
    assert intro.details["instructors"] == "Staff"
    assert intro.details["equivalents"] == "FHIS 10100"
    assert by["FSCI 10200"].details["prerequisites"] == "FSCI 10100 or FSCI 10150"
    assert by["FSCI 10200"].details["notes"] == "FAKE note."
    assert problems == ["course title line not understood: 'FSCI 2x100. Broken Title Line'"]


def test_staged_catalog_has_crosslists_relations_and_problems() -> None:
    staged = parse_courses(
        "2099-00",
        [
            page("thecollege/fakescience", "1"),
            page("thecollege/fakehistory", "2"),
            page("thecollege/fakecourses", "3"),
        ],
    )
    assert len(staged.courses) == 8
    fsci = staged.courses["FSCI 10100"]
    assert fsci.terms_offered == ["AU", "WI"]
    assert fsci.crosslists == ["FHIS 10100"]
    assert fsci.source == {
        "snapshot_id": "1",
        "url": "http://catalog.test/thecollege/fakescience/",
        "quote": "FSCI 10100. Fake Science I. 100 Units.",
    }
    assert staged.courses["FSCI 29900"].units == 50
    assert staged.courses["FSCI 20100"].terms_offered == ["SP", "SU"]
    assert staged.crosslist_groups == [["FHIS 10100", "FSCI 10100"]]
    kinds = {(r.a, r.b, r.kind) for r in staged.relations}
    assert ("FSCI 10100", "FSCI 10150", "mutually_exclusive") in kinds
    # "replaces FSCI 19900" names a course that does not exist: no relation is invented.
    assert all(r.kind != "replaces" for r in staged.relations)
    rel = next(r for r in staged.relations if r.kind == "mutually_exclusive")
    assert rel.source["quote"].startswith("Students may not receive credit for both")
    assert any("Broken Title Line" in p for p in staged.problems)


def test_course_batches_diff_against_last_year() -> None:
    staged = parse_courses("2099-00", [page("thecollege/fakehistory", "2")])
    before = {code: c.comparable() for code, c in staged.courses.items()}
    unchanged = course_batches(staged, before, previous_year="2098-99")
    assert [d.target_id for d in unchanged] == ["2099-00:FHIS"]
    assert unchanged[0].diff["unchanged"] is True
    assert "no changes" in unchanged[0].reason

    before["FHIS 20100"] = {**before["FHIS 20100"], "title": "Old Empires"}
    before["FHIS 30000"] = {"code": "FHIS 30000", "title": "Gone"}
    del before["FHIS 20200"]
    drafts = course_batches(
        staged,
        before,
        previous_year="2098-99",
        requisites={"FHIS 20100": {"prereq": {}, "raw_text": "FHIS 10100"}},
    )
    diff = drafts[0].diff
    assert diff["added"] == ["FHIS 20200"]
    assert diff["removed"] == ["FHIS 30000"]
    assert diff["changed"][0]["code"] == "FHIS 20100" and diff["changed"][0]["fields"] == ["title"]
    assert diff["requisites"] == {"FHIS 20100": {"prereq": {}, "raw_text": "FHIS 10100"}}
    assert drafts[0].reason == "FHIS: 1 new, 1 changed, 1 removed since 2098-99"


# ------------------------------------------------------------------------- snapshots


def test_sigv4_matches_the_published_aws_example() -> None:
    headers = {
        "host": "examplebucket.s3.amazonaws.com",
        "range": "bytes=0-9",
        "x-amz-content-sha256": EMPTY_SHA256,
        "x-amz-date": "20130524T000000Z",
    }
    auth = sigv4_authorization(
        method="GET",
        url="https://examplebucket.s3.amazonaws.com/test.txt",
        headers=headers,
        payload_sha256=EMPTY_SHA256,
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        amz_date="20130524T000000Z",
    )
    assert auth.endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date" in auth


def test_minio_store_puts_signed_objects() -> None:
    seen: list[httpx.Request] = []
    objects: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "PUT" and request.url.path == "/snapshots":
            return httpx.Response(409)  # the bucket exists already
        if request.method == "PUT":
            objects[request.url.path] = request.content
            return httpx.Response(200)
        return httpx.Response(200, content=objects[request.url.path])

    store = MinioStore(
        endpoint="minio.test:9000",
        access_key="key",
        secret_key="secret",
        bucket="snapshots",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: dt.datetime(2026, 8, 1, tzinfo=dt.UTC),
    )
    store.put("catalog/ab/abc", b"<html>FAKE</html>", "text/html")
    assert store.get("catalog/ab/abc") == b"<html>FAKE</html>"
    put = seen[1]
    assert put.headers["authorization"].startswith(
        "AWS4-HMAC-SHA256 Credential=key/20260801/us-east-1/s3/aws4_request"
    )
    assert put.headers["x-amz-content-sha256"] == hashlib.sha256(b"<html>FAKE</html>").hexdigest()
    assert put.headers["content-type"] == "text/html"


def test_archive_keys_are_content_addressed() -> None:
    archive = memory_archive()
    a = archive.save("http://catalog.test/a/", 200, b"same", "text/html")
    b = archive.save("http://catalog.test/b/", 200, b"same", "text/html")
    assert a.id != b.id and a.storage_key == b.storage_key
    assert archive.get(a.id).url == "http://catalog.test/a/"
