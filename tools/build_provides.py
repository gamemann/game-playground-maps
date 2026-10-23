#!/usr/bin/env python3
"""Writes provides.json, the Workshop listing of this pack: one `map` entry per document in DIR.

    tools/build_provides.py            # rewrite provides.json
    tools/build_provides.py --check    # exit 1 if it is not what this would write, or an entry is bad

The entries come from the documents on disk, so a map added by the other builders is listed with
no second edit. `scene` is relative to the pack root, as the publisher requires.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = 'Playground maps'
GAMES = ["gamemann/game-playground"]
DIR = 'maps'
DOC_KIND = "playground_map"  # the document's own "kind" a listed one must have; None lists every .json
MAP_KIND = lambda d: d["map_kind"]  # the entry's map_kind, or a callable taking the document


def build():
    entries = []
    for name in sorted(os.listdir(os.path.join(ROOT, DIR))):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(ROOT, DIR, name)) as f:
            doc = json.load(f)
        if DOC_KIND is not None and doc.get("kind") != DOC_KIND:
            continue
        mid = name[:-5]
        kind = MAP_KIND(doc) if callable(MAP_KIND) else MAP_KIND
        entries.append({"kind": "map", "id": mid, "name": doc.get("name") or mid, "scene": DIR + "/" + name, "map_kind": kind})
    return {"schema": 1, "title": TITLE, "kinds": ["map"], "games": GAMES, "entries": entries}


def problems(doc):
    bad = []
    seen = set()
    for e in doc["entries"]:
        if not re.fullmatch(r"[a-z0-9_]+", e["id"]) or e["id"] in seen:
            bad.append("bad or repeated id " + e["id"])
        seen.add(e["id"])
        if not e["map_kind"]:
            bad.append("no map_kind for " + e["id"])
        if not os.path.isfile(os.path.join(ROOT, e["scene"])):
            bad.append("missing " + e["scene"])
    if not doc["entries"]:
        bad.append("no entries")
    return bad


def main():
    doc = build()
    text = json.dumps(doc, indent=4) + "\n"
    path = os.path.join(ROOT, "provides.json")
    bad = problems(doc)
    if "--check" in sys.argv:
        have = open(path).read() if os.path.exists(path) else ""
        if have != text:
            bad.append("provides.json is stale (run tools/build_provides.py)")
        for b in bad:
            print(b)
        print("provides.json ok, %d maps" % len(doc["entries"]) if not bad else "provides.json FAILED")
        return 1 if bad else 0
    if bad:
        print("\n".join(bad))
        return 1
    with open(path, "w") as f:
        f.write(text)
    print("wrote provides.json, %d maps" % len(doc["entries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
