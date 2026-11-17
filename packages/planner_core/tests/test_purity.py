"""Guards the hard rule: planner_core never imports I/O, web, DB or LLM libraries."""

import ast
from pathlib import Path

import planner_core

FORBIDDEN = {
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "alembic",
    "redis",
    "arq",
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "requests",
    "aiohttp",
    "urllib3",
    "anthropic",
    "openai",
    "llm_gateway",
    "api",
    "worker",
    "scraper",
    "socket",
    "subprocess",
    "yaml",
}
FORBIDDEN_FROM = {("urllib", "request"), ("http", "client")}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def test_planner_core_has_no_forbidden_imports() -> None:
    root = Path(planner_core.__file__).parent
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for name in _imports(path):
            parts = name.split(".")
            if parts[0] in FORBIDDEN or tuple(parts[:2]) in FORBIDDEN_FROM:
                offenders.append(f"{path.relative_to(root)}: {name}")
    assert offenders == []


def test_core_version_is_stable_string() -> None:
    assert planner_core.CORE_VERSION.startswith("planner_core-")
