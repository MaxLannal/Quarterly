"""CLI used by the Makefile: `make seed`, `make golden`, `make api-client` (schemas)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def cmd_seed(args: argparse.Namespace) -> int:
    from api.seed.bundle import SeedError, discover, integrity, load_bundle

    years = discover(args.dir)
    if not years:
        print(f"seed: no catalog years in {args.dir}")
        return 0
    status = 0
    for year_dir in years:
        try:
            bundle = load_bundle(year_dir)
        except SeedError as exc:
            print(f"seed: {exc}")
            return 1
        errors, warnings = integrity(bundle)
        for w in warnings:
            print(f"seed: warning: {w}")
        if errors:
            for e in errors:
                print(f"seed: error: {e}")
            print(f"seed: {year_dir.name}: {len(errors)} errors, nothing loaded")
            status = 1
            continue
        if args.dry_run:
            n_courses, n_programs = len(bundle.courses), len(bundle.programs)
            print(f"seed: {year_dir.name}: valid ({n_courses} courses, {n_programs} programs)")
            continue
        from sqlalchemy.orm import Session

        from api.db.session import get_engine
        from api.seed.loader import upsert_bundle

        with Session(get_engine(args.database_url)) as session:
            counts = upsert_bundle(session, bundle)
        print(f"seed: {year_dir.name}: loaded " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return status


def cmd_golden(args: argparse.Namespace) -> int:
    from api.golden import run_golden

    return run_golden(args.golden_dir, args.seed_dir)


def cmd_schemas(args: argparse.Namespace) -> int:
    from api.schema_export import export

    for name, schema in export().items():
        (args.out / f"{name}.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"schemas: wrote {len(export())} JSON Schemas to {args.out}")
    return 0


def cmd_seed_forum_demo(args: argparse.Namespace) -> int:
    from sqlalchemy.orm import Session

    from api.db.session import get_engine
    from api.forum.demo import DemoRefusedError, remove_demo, seed_demo

    try:
        with Session(get_engine(args.database_url)) as session:
            if args.remove:
                print(f"seed-forum-demo: removed {remove_demo(session)} fake instructors")
                return 0
            counts = seed_demo(session)
    except DemoRefusedError as exc:
        print(f"seed-forum-demo: refused: {exc}")
        return 1
    print(
        "seed-forum-demo: FAKE demo data loaded: "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
    )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed", help="validate and upsert data/seed/<catalog_year>/")
    seed.add_argument("--dir", type=Path, default=REPO_ROOT / "data" / "seed")
    seed.add_argument("--database-url", default=None)
    seed.add_argument("--dry-run", action="store_true")
    seed.set_defaults(func=cmd_seed)
    golden = sub.add_parser("golden", help="run golden plans")
    golden.add_argument("--golden-dir", type=Path, default=REPO_ROOT / "data" / "golden")
    golden.add_argument("--seed-dir", type=Path, default=REPO_ROOT / "data" / "seed")
    golden.set_defaults(func=cmd_golden)
    schemas = sub.add_parser("schemas", help="export JSON Schemas")
    schemas.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "schemas")
    schemas.set_defaults(func=cmd_schemas)
    demo = sub.add_parser(
        "seed-forum-demo",
        help="development only: fake instructors and forum pages on a few real courses",
    )
    demo.add_argument("--database-url", default=None)
    demo.add_argument("--remove", action="store_true", help="delete the fake demo data")
    demo.set_defaults(func=cmd_seed_forum_demo)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
