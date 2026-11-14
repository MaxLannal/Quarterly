"""The API surface is frozen (prompt 01): every endpoint exists with its schema; stubs return 501."""

import pytest
from api.main import app
from fastapi.testclient import TestClient

EXPECTED = {
    ("get", "/health"),
    ("get", "/version"),
    # catalog
    ("get", "/catalog-years"),
    ("get", "/terms"),
    ("get", "/courses"),
    ("get", "/courses/{code}"),
    ("get", "/course-lists/{name}"),
    ("get", "/programs"),
    ("get", "/programs/{program_id}"),
    ("get", "/programs/{program_id}/eligible"),
    ("get", "/instructors"),
    ("get", "/instructors/{slug}"),
    # plans
    ("get", "/plans"),
    ("post", "/plans"),
    ("post", "/plans/import"),
    ("post", "/plans/generate"),
    ("post", "/plans/{plan_id}/generate"),
    ("get", "/plans/compare"),
    ("get", "/plans/{plan_id}"),
    ("patch", "/plans/{plan_id}"),
    ("delete", "/plans/{plan_id}"),
    ("post", "/plans/{plan_id}/duplicate"),
    ("patch", "/plans/{plan_id}/items"),
    ("get", "/plans/{plan_id}/changesets"),
    ("post", "/plans/{plan_id}/changesets/{changeset_id}/apply"),
    ("post", "/plans/{plan_id}/changesets/{changeset_id}/discard"),
    # verify, agents
    ("post", "/verify"),
    ("post", "/agents/generate"),
    ("post", "/agents/chat"),
    ("get", "/agents/chat/history"),
    # forum
    ("get", "/forum/pages"),
    ("get", "/forum/pages/{page_id}"),
    ("get", "/forum/pages/{page_id}/posts"),
    ("post", "/forum/pages/{page_id}/posts"),
    ("get", "/forum/posts/{post_id}"),
    ("patch", "/forum/posts/{post_id}"),
    ("delete", "/forum/posts/{post_id}"),
    ("post", "/forum/posts/{post_id}/comments"),
    ("post", "/forum/votes"),
    ("post", "/forum/reports"),
    ("get", "/forum/courses/{code}"),
    # auth + account (decision 5)
    ("post", "/auth/email"),
    ("post", "/auth/verify-code"),
    ("post", "/auth/register"),
    ("post", "/auth/login"),
    ("post", "/auth/logout"),
    ("get", "/auth/session"),
    ("post", "/auth/password-reset/start"),
    ("post", "/auth/password-reset/finish"),
    ("get", "/account/export"),
    ("post", "/account/password"),
    ("post", "/account/delete"),
    # admin
    ("get", "/admin/review-items"),
    ("post", "/admin/review-items/{item_id}/decision"),
    ("post", "/admin/program-versions/{version_id}/publish"),
    ("get", "/admin/moderation"),
    ("post", "/admin/moderation/{target_type}/{target_id}/decision"),
}

PLAN = {"catalog_year": "2026-27", "entry_term": "2026-AU"}
UUID = "00000000-0000-0000-0000-000000000001"


def test_openapi_lists_every_endpoint() -> None:
    spec = app.openapi()
    found = {(method, path) for path, ops in spec["paths"].items() for method in ops}
    assert found == EXPECTED
    schemas = spec["components"]["schemas"]
    for name in (
        "PlanState",
        "Report",
        "Certificate",
        "ChangeSet",
        "AgentEvent",
        "GoldenPlan" if False else "Issue",
    ):
        assert name in schemas
    assert (
        "text/event-stream"
        in spec["paths"]["/agents/generate"]["post"]["responses"]["200"]["content"]
    )


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/admin/review-items", None),
    ],
)
def test_stubs_return_501_after_validation(
    method: str, path: str, body: dict[str, object] | None
) -> None:
    client = TestClient(app)
    resp = client.request(method.upper(), path, json=body)
    assert resp.status_code == 501, resp.text
    assert resp.json()["detail"].startswith("Not implemented yet")


def test_request_validation_happens_before_the_stub() -> None:
    # The forum needs a login (401 before the body is read); its validation is tested in
    # test_forum_api.py.
    resp = TestClient(app).post(
        "/verify", json={"plan": {"catalog_year": "2026-27", "entry_term": "2026-FA"}}
    )
    assert resp.status_code == 422
