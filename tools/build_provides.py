#!/usr/bin/env python3
"""Writes provides.json, the Workshop listing; the logic is dot-map's tools/build_provides.py.

    tools/build_provides.py            # rewrite
    tools/build_provides.py --check    # exit 1 if stale or an entry is bad

dot-map is a sibling checkout (`../dot-map`, where dot-bootstrap clones it) or `$DOTMAP_PATH`.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = 'Playground maps'
GAMES = ["gamemann/game-playground"]
DIR = 'maps'
DOC_KIND = "playground_map"  # the document's own "kind" a listed one must have; None lists every .json
MAP_KIND = lambda d: d["map_kind"]  # the entry's map_kind, or a callable taking the document


for _p in (os.environ.get("DOTMAP_PATH", ""), os.path.join(ROOT, "..", "dot-map")):
    if _p and os.path.isfile(os.path.join(_p, "tools", "build_provides.py")):
        sys.path.insert(0, os.path.join(_p, "tools"))
        break
else:
    sys.exit("build_provides: dot-map was not found. Clone it beside this repository or set DOTMAP_PATH.")
import build_provides  # noqa: E402

sys.exit(build_provides.run(ROOT, GAMES, title=TITLE, directory=DIR, doc_kind=DOC_KIND, map_kind=MAP_KIND))
