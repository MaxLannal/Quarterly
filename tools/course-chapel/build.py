"""Build apps/web/public/home/course-chapel.json: the homepage chapel drawn with course titles.

Inputs (nothing is fetched):
  - tools/course-chapel/scene.rockefeller.json: the chapel drawing from tools/ascii-scene
    (colour, scene class and stained-glass code per cell). Before launch the drawing must come from
    our own photo (docs/OPEN_QUESTIONS.md DF-A1): convert it with tools/ascii-scene/tools/convert.py
    and save the result here, then run this script again.
  - data/seed/2026-27/courses/*.yaml: course codes and titles, exactly as seeded (titles are
    not edited, only an encoding slip is mapped: U+0096 to an en dash).

Output: the finest level of the drawing (cell colours, classes, glow codes) and a fixed,
shuffled sample of real course titles with their codes, so a title on the homepage can open its
course page.

Run from the repository root:  python3 tools/course-chapel/build.py
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "tools/course-chapel/scene.rockefeller.json"
SEED = ROOT / "data/seed/2026-27/courses"
OUT = ROOT / "apps/web/public/home/course-chapel.json"

# Enough titles to fill a 2560 x 1440 screen without an obvious repeat; about 30 KB gzipped.
SAMPLE = 1600
SHUFFLE_SEED = 2026
# Newsreader (the glyph font) covers Basic Latin, Latin-1 and Latin Extended-A; a title with any
# other character (for example U+30FB) is left out rather than drawn with a missing glyph.
DRAWABLE = re.compile(r"^[\u0020-\u007e\u00a0-\u017f\u2013\u2014\u2018\u2019\u201c\u201d\u201e]+$")
# Course codes to leave out of the picture (it shows real titles as they are in the catalog; add a
# code here to keep a title off the homepage, then run this script again).
EXCLUDE: set[str] = set()
# The main facade with the two front spires, in image fractions (cols 33-90 of 190 at the finest
# level). Phones frame this part; wider screens frame the whole chapel.
FACADE = {"x0": 0.175, "x1": 0.475}
# Where the chapel's masses meet, in image fractions, read off the drawing's roofline: the front
# with its spires ends where the nave roof starts to fall (col 79 of 190), and the nave meets the
# tower behind it where the roofline rises again (col 99). The picture gives each mass its own
# depth and light, so the chapel reads as a building rather than a flat shape.
MASSES = {"frontEnd": 0.416, "towerStart": 0.521}


def courses() -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for path in sorted(SEED.glob("*.yaml")):
        for course in yaml.safe_load(path.read_text())["courses"]:
            title = " ".join(str(course["title"]).replace("\u0096", "\u2013").split())
            key = title.casefold()
            if str(course["code"]) in EXCLUDE:
                continue
            if key in seen or not 6 <= len(title) <= 64 or not DRAWABLE.match(title):
                continue
            seen.add(key)
            out.append((str(course["code"]), title))
    random.Random(SHUFFLE_SEED).shuffle(out)
    return out[:SAMPLE]


def chapel_bounds(cols: int, rows: int, cls: str) -> dict[str, float]:
    xs = [i % cols for i, c in enumerate(cls) if c == "1"]
    ys = [i // cols for i, c in enumerate(cls) if c == "1"]
    return {
        "x0": round(min(xs) / cols, 4),
        "x1": round((max(xs) + 1) / cols, 4),
        "y0": round(min(ys) / rows, 4),
        "y1": round((max(ys) + 1) / rows, 4),
    }


def main() -> int:
    scene = json.loads(SCENE.read_text())
    level = max(scene["levels"], key=lambda lv: lv["cols"])
    cols, rows = level["cols"], level["rows"]
    picked = courses()
    if len(picked) < SAMPLE:
        print(f"only {len(picked)} drawable titles in the seed", file=sys.stderr)
        return 1
    chapel = chapel_bounds(cols, rows, level["cls"])
    data = {
        "version": 1,
        "source": "tools/course-chapel/build.py",
        "field": {
            "cols": cols,
            "rows": rows,
            # width / height of the source image, so cells can be mapped back to its shape
            "aspect": round(scene["w"] / scene["h"], 5),
            "baseline": scene["baseline"],
            "rgb": level["rgb"],
            "cls": level["cls"],
            "glow": level["glow"],
        },
        "chapel": chapel,
        "facade": {**FACADE, "y0": chapel["y0"], "y1": chapel["y1"]},
        "masses": MASSES,
        "courses": [[code, title] for code, title in picked],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {cols}x{rows} cells, {len(picked)} titles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
