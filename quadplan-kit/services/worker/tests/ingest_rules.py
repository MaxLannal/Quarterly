"""A FAKE program (Fake Science BS) used by the agent tests, quoted from the FAKE fixture page
`fixtures/catalog/thecollege/fakescience/`."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
from pathlib import Path
from typing import Any

import yaml
from planner_core.models import CourseList, ProgramRules
from worker.ingest.catalog import CatalogView, CourseFacts
from worker.ingest.e2 import ProgramCandidate
from worker.ingest.snapshots import Snapshot

URL = "http://catalog.test/thecollege/fakescience/"
FIX = Path(__file__).parent / "fixtures" / "catalog"


def fake_page(rel: str = "thecollege/fakescience", sid: str = "7", url: str = URL) -> Snapshot:
    body = (FIX / rel / "index.html").read_bytes()
    return Snapshot(
        id=sid,
        url=url,
        fetched_at=dt.datetime(2099, 8, 1, tzinfo=dt.UTC),
        sha256=hashlib.sha256(body).hexdigest(),
        storage_key="catalog/x",
        content_type="text/html",
        status=200,
        body=body,
    )


RULES: dict[str, Any] = {
    "id": "fsci-bs",
    "catalog_year": "2099-00",
    "type": "major",
    "rules": {
        "id": "fsci-bs",
        "label": "Fake Science BS",
        "group": {
            "all": True,
            "children": [
                {
                    "id": "intro",
                    "group": {
                        "all": True,
                        "children": [
                            {
                                "id": "1",
                                "slot": {"any_of": ["FSCI 10100", "FSCI 10150"]},
                                "source": {"url": URL, "quote": "FSCI 10100"},
                            },
                            {
                                "id": "2",
                                "slot": {"any_of": ["FSCI 10200"]},
                                "source": {"url": URL, "quote": "FSCI 10200"},
                            },
                        ],
                    },
                    "source": {
                        "url": URL,
                        "quote": "Students who major in fake science must complete the introductory sequence:",
                    },
                },
                {
                    "id": "methods",
                    "slot": {"any_of": ["FSCI 20100"]},
                    "constraints": {"no_pass_fail": True},
                    "source": {"url": URL, "quote": "The BS also requires FSCI 20100."},
                },
            ],
        },
        "source": {
            "url": URL,
            "quote": "The fake science program offers BA and BS degrees and a minor.",
        },
    },
}


def rules(**changes: Any) -> ProgramRules:
    data = copy.deepcopy(RULES)
    data.update(changes)
    return ProgramRules.model_validate(data)


def rules_yaml(data: dict[str, Any] | None = None) -> str:
    return yaml.safe_dump(data or RULES, sort_keys=False)


def catalog(year: str = "2099-00") -> CatalogView:
    codes = ["FSCI 10100", "FSCI 10150", "FSCI 10200", "FSCI 20100", "FHIS 10100", "FHIS 20100"]
    return CatalogView.build(
        year,
        [CourseFacts(c, f"Fake {c}") for c in codes],
        [CourseList(name="fake-list", courses=["FSCI 10100", "FSCI 10200"])],
    )


def candidate(**kw: Any) -> ProgramCandidate:
    data = {
        "id": "fsci-bs",
        "name": "Fake Science (BS)",
        "type": "major",
        "degree": "BS",
        "family": "Fake Science",
        "url": URL,
        "evidence": [],
    }
    data.update(kw)
    return ProgramCandidate.model_validate(data)
