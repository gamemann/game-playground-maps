#!/usr/bin/env python3
"""The VBSP reader this repository's importer uses, which is the converter's shared one.

`dot-map-convert/dotbsp/reader.py` reads the format (v19-v21, LZMA, both v21 lump orders,
displacements, static props) for every game's converter, so a fix to how a map is read
reaches all of them. This file only keeps the name the importer imports
(`import bsp_read; bsp_read.Bsp(path).load()`).

It used to be a 565-line copy of the reader, one of six identical copies in the map
repositories; each drifted from the others' fixes, which is why the reader moved to dot-map-convert.
Do not put reading code back here: fix it in dot-map-convert, where every game gets it.

dot-map-convert is found as a sibling checkout (`../dot-map-convert`, where dot-bootstrap clones it) or at
`$DOTBSP_PATH` (dot-map-convert).
"""
import os
import sys


def _shared():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.environ.get("DOTBSP_PATH", ""), os.path.join(here, "..", "..", "dot-map-convert")):
        if p and os.path.isfile(os.path.join(p, "dotbsp", "reader.py")):
            return os.path.abspath(p)
    sys.exit("bsp_read: dot-map-convert's shared reader was not found. Clone dot-map-convert beside this "
             "repository (dot-bootstrap does) or set DOTBSP_PATH to dot-map-convert.")


if _shared() not in sys.path:
    sys.path.insert(0, _shared())

from dotbsp.reader import *  # noqa: E402,F401,F403
