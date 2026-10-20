#!/usr/bin/env python3
"""Converts a Source 1 community sandbox .bsp (VBSP 19/20) into a game-playground map document.

    tools/import_bsp.py <map.bsp> <config-name> [--out=maps/<id>.json]

`CONFIGS` below says, per map, its id, name, author, page, how its author's textures become the
game's materials, where the spawn is and what is dropped. The reader (bsp_read.py) and the material
naming and majority pick (dotbsp.docboxes) are dot-map's shared ones. The box helpers below stay
local on purpose: dotbsp.boxes.decompose(tilt=True) cuts a slope along the slope's own axis and
spans each slab's cross-section, where these cut along the longer axis across the bounding box,
so it would change the committed boxes (a re-import of every map must stay byte-identical).

What it does, and why each choice:

- A document has boxes and no meshes, so each world brush becomes a BOX: its convex hull is
  found (bsp_read.Bsp.brush_hull) and, when every corner is a box corner, that box is written;
  a box turned about the vertical axis keeps its turn; a prism of any plan is the smallest
  turned rectangle round it; anything else (a slope, a stair) is cut into slabs along its longer
  horizontal axis, each as tall as the brush is at the slab's middle, so a ramp becomes a flight
  of 0.5 m risers, which a player climbs (the game's climb limit is 1.035 m).
- Axes: Source is Z-up, godot is (x, z, -y). Scale: 1 unit = 0.01905 m, the family's.
- Textures are NOT carried. The author's textures are replaced by the game's materials by name
  (CONFIGS[...]["textures"]), drawn over Kenney's CC0 Prototype Textures grid like every other map.
- Tool brushes (skybox, clip, trigger, hint, nodraw-only) are dropped. A water brush becomes a
  water volume. Displacements are not carried (a document has no meshes); the brush under one is.
- The ground is shifted so the spawn's floor is y = 0.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bsp_read  # noqa: E402  (also puts dot-map's tools/bsp on sys.path)
from dotbsp import docboxes  # noqa: E402  (the passes the map repositories share)

S = 0.01905
SLAB = 28.0     # source units: ~0.53 m, a slope's riser
MIN_SIDE = 0.04  # metres: a brush thinner than this in every direction is a bevel sliver, not a wall


def planes_of(bsp, index):
    first, count, _ = bsp.brushes[index]
    return [bsp.planes[s[0]][:4] for s in bsp.brushsides[first:first + count] if not s[3]]


def z_range(planes, x, y):
    lo, hi = -1e9, 1e9
    for nx, ny, nz, d in planes:
        if abs(nz) < 1e-6:
            continue
        z = (d - nx * x - ny * y) / nz
        if nz > 0:
            hi = min(hi, z)
        else:
            lo = max(lo, z)
    return lo, hi


def box_in_frame(pts, phi, tol):
    """The hull's extents in a frame turned phi degrees about z, or None when some corner is not
    a corner of that bounding box. (x0, x1), (y0, y1), (z0, z1), in the turned frame."""
    c, sn = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    q = [(p[0] * c + p[1] * sn, -p[0] * sn + p[1] * c, p[2]) for p in pts]
    x0, x1 = min(p[0] for p in q), max(p[0] for p in q)
    y0, y1 = min(p[1] for p in q), max(p[1] for p in q)
    z0, z1 = min(p[2] for p in q), max(p[2] for p in q)
    for p in q:
        if not ((abs(p[0] - x0) < tol or abs(p[0] - x1) < tol) and (abs(p[1] - y0) < tol or abs(p[1] - y1) < tol)
                and (abs(p[2] - z0) < tol or abs(p[2] - z1) < tol)):
            return None
    return (x0, x1), (y0, y1), (z0, z1)


def turned_box(bsp, index, pts):
    """(box, phi) when the brush is a box turned about the vertical axis, else None. The author's
    building is not always on the grid (a room at thirty degrees to the rest), and cutting such a
    wall into axis-aligned slabs gives a saw-tooth the players catch on. The angle is each upright
    side's direction modulo 90, tried in turn; the document's boxes carry a yaw."""
    first, count, _ = bsp.brushes[index]
    tried = set()
    for sd in bsp.brushsides[first:first + count]:
        if sd[3]:
            continue
        nx, ny, nz, _d = bsp.planes[sd[0]][:4]
        if abs(nz) > 1e-4:
            continue
        phi = round(math.degrees(math.atan2(ny, nx)) % 90.0, 2)
        if phi in tried or phi < 0.05 or phi > 89.95:
            continue
        tried.add(phi)
        # Four-decimal planes at 1000 units leave a unit of slack in the corners.
        box = box_in_frame(pts, phi, 1.5)
        if box is not None:
            return box, phi
    return None


def prism_box(pts):
    """(box, phi) for a brush that is a vertical prism of any plan shape: the smallest turned
    rectangle round its plan. A curved wall is a run of such wedges and a column of a round room
    is one; the box overhangs the wedge by a sliver, where cutting it into axis-aligned slabs (a
    slope's treatment, wrong for a plan shape) bit chunks out of the room. None for a brush whose
    top or bottom is not flat and level."""
    zs = sorted({round(p[2], 1) for p in pts})
    if len(zs) != 2:
        return None
    low = {(round(p[0], 1), round(p[1], 1)) for p in pts if abs(p[2] - zs[0]) < 0.15}
    high = {(round(p[0], 1), round(p[1], 1)) for p in pts if abs(p[2] - zs[1]) < 0.15}
    if low != high or len(low) < 3:
        return None
    plan = [(x, y, zs[0]) for x, y in low]
    best = None
    for (ax, ay), (bx_, by) in ((p, q) for p in low for q in low if p != q):
        phi = math.degrees(math.atan2(by - ay, bx_ - ax)) % 90.0
        box = box_in_frame(plan, phi, 1e9)
        area = (box[0][1] - box[0][0]) * (box[1][1] - box[1][0])
        if best is None or area < best[0] - 1e-6:
            best = (area, phi, box)
    _a, phi, box = best
    return (box[0], box[1], (zs[0], zs[1])), phi


def ramp_box(bsp, index, pts):
    """A tilted box for a wedge whose only sloping face is a plane rising along one world axis:
    (x0, x1, y0, y1, zlow, zhigh, base, angle in degrees, axis 'x' or 'y', sign), else None. One
    tilted box is the ramp's surface exactly; the staircase of slabs it replaces left a 0.5 m gap
    between every slab and the one after next, which the survey reads as a row of slots, and a
    player's feet catch on its saw-tooth. The box hangs under the surface, so the sliver it
    overhangs past the high end is inside the wall the ramp meets."""
    sloped = [p for p in planes_of(bsp, index) if 0.05 < p[2] < 0.98]
    if len(sloped) != 1:
        return None
    nx, ny, nz, d = sloped[0]
    if (abs(nx) > 1e-3) == (abs(ny) > 1e-3):
        return None
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    base = min(p[2] for p in pts)
    along_x = abs(nx) > 1e-3
    g = -(nx if along_x else ny) / nz
    if along_x:
        za, zb = (d - nx * x0) / nz, (d - nx * x1) / nz
    else:
        za, zb = (d - ny * y0) / nz, (d - ny * y1) / nz
    return (x0, x1, y0, y1, za, zb, base, math.degrees(math.atan(abs(g))), "x" if along_x else "y", 1 if g > 0 else -1)


def brush_boxes(bsp, index, slab=None):
    """[((x range), (y range), (z range), phi)] in Source units, the ranges in a frame turned phi
    degrees (0 for most), and whether the brush had to be cut into slabs."""
    pts = bsp.brush_hull(index)
    if len(pts) < 4:
        return [], 0
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
    box_vol = (x1 - x0) * (y1 - y0) * (z1 - z0)
    # Hull volume from the corner points: a brush is a box when every corner is a box corner.
    corners = sum(1 for p in pts if (abs(p[0] - x0) < 0.5 or abs(p[0] - x1) < 0.5) and (abs(p[1] - y0) < 0.5 or abs(p[1] - y1) < 0.5) and (abs(p[2] - z0) < 0.5 or abs(p[2] - z1) < 0.5))
    if corners == len(pts):
        return [((x0, x1), (y0, y1), (z0, z1), 0.0)], 0
    tb = turned_box(bsp, index, pts)
    if tb is not None:
        return [tb[0] + (tb[1],)], 0
    pb = prism_box(pts)
    if pb is not None:
        return [pb[0] + (pb[1],)], 0
    rb = ramp_box(bsp, index, pts)
    if rb is not None:
        return [rb], 2
    pl = planes_of(bsp, index)
    out = []
    if x1 - x0 >= y1 - y0:
        n = max(1, math.ceil((x1 - x0) / (slab or SLAB)))
        for i in range(n):
            a, b = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n
            lo, hi = z_range(pl, (a + b) / 2, (y0 + y1) / 2)
            lo, hi = max(lo, z0), min(hi, z1)
            if hi - lo > 0.5:
                out.append(((a, b), (y0, y1), (lo, hi), 0.0))
    else:
        n = max(1, math.ceil((y1 - y0) / (slab or SLAB)))
        for i in range(n):
            a, b = y0 + (y1 - y0) * i / n, y0 + (y1 - y0) * (i + 1) / n
            lo, hi = z_range(pl, (x0 + x1) / 2, (a + b) / 2)
            lo, hi = max(lo, z0), min(hi, z1)
            if hi - lo > 0.5:
                out.append(((x0, x1), (a, b), (lo, hi), 0.0))
    return out, 1


# Per map. "textures" is (substring of the classified texture name, material, colour or None),
# first match wins; the material is one of the game's, so the look is Kenney's grid under a tint.
CONFIGS = {
    "construct_small": {
        "id": "pgc_construct_small",
        "name": "Construct Small",
        "blurb": "A pool pit and a brick plant house under open sky: a concrete yard with a deep water basin, a long brick-walled lane and a grass field behind, ringed by tall plaster walls.",
        "author": "Wylie",
        "source": "gm_construct_small, https://gamebanana.com/mods/60385",
        "spawn_at": 0,
        # The basin is 8.5 m deep with a wall all round: a player thrown in could never leave, so
        # one ramp is added (metres in the document's frame).
        "ramps": [{"x": (-27.0, -9.75), "z": (-30.0, -26.0), "y": (-8.53, 0.0)}],
        # Tops of the tall outer walls and a rail, which no player is meant to stand on.
        "declared": [
            {"min": [-30.9, 18.9, -39.1], "max": [29.7, 20.1, 10.0], "why": "tops of the plaster walls"},
            {"min": [-0.5, 8.1, -29.5], "max": [0.7, 9.3, -1.0], "why": "the rail along the lane"},
            {"min": [-31.0, 29.1, -40.7], "max": [60.2, 30.3, 11.5], "why": "the tops of the tall outer walls"},
        ],
        "textures": [
            ("WATER", "water", None),
            ("FLATGRASS", "grass", None),
            ("BRICK", "rock", "#b0705a"),
            ("PLASTER", "concrete", "#d9d2c3"),
            ("CONCRETECEILING", "concrete", "#8d8b86"),
            ("CONCRETE", "concrete", None),
            ("REFLECTIVITY", "concrete", "#a9aaae"),
        ],
        "default": ("concrete", None),
    },
}

WATER = 0x20


def material_for(cfg, names):
    # The majority pick (sorted, so a tie follows the name, not the hash seed) is dot-map's.
    return docboxes.majority_material(names, cfg["textures"], cfg["default"])


def ramp_document_box(rb, mat, colour, y_off):
    """The document box for a [method ramp_box]: its top face is the sloped face, dropped along
    its own normal by half the thickness."""
    x0, x1, y0, y1, za, zb, base, ang, axis, sign = rb
    run = (x1 - x0) if axis == "x" else (y1 - y0)
    width = (y1 - y0) if axis == "x" else (x1 - x0)
    length = math.hypot(run, abs(zb - za))
    thick = max((max(za, zb) - base) * math.cos(math.radians(ang)), 8.0)
    # Surface midpoint, source units, then the normal in godot axes (x, z, -y).
    mx, my, mz = (x0 + x1) / 2, (y0 + y1) / 2, (za + zb) / 2
    t = math.radians(ang) * sign
    if axis == "x":
        n = (-math.sin(t), math.cos(t), 0.0)
        size = [length, thick, width]
        turn = [0, 0, 1, round(math.degrees(t), 2)]
    else:
        n = (0.0, math.cos(t), -math.sin(t))
        size = [width, thick, length]
        turn = [1, 0, 0, round(math.degrees(t), 2)]
    top = (mx * S, mz * S - y_off, -my * S)
    at = [round(top[k] - n[k] * thick * S / 2, 3) for k in range(3)]
    b = {"at": at, "size": [round(v * S, 3) for v in size], "material": mat, "turn": turn}
    if colour:
        b["colour"] = colour
    return b


def snap(b, grid=0.01):
    """Round an upright box's faces to a grid, so two brushes that meet in the author's map meet
    here: a face 0.4 mm short of its neighbour is a crack the survey reads as a slot."""
    if "turn" in b and b["turn"][3]:
        return b
    for k in range(3):
        lo = round((b["at"][k] - b["size"][k] / 2) / grid) * grid
        hi = round((b["at"][k] + b["size"][k] / 2) / grid) * grid
        if hi > lo:
            b["at"][k], b["size"][k] = round((lo + hi) / 2, 3), round(hi - lo, 3)
    return b


def build(bsp_path, name):
    cfg = CONFIGS[name]
    bsp = bsp_read.Bsp(bsp_path).load()
    starts = [e for e in bsp.entities if e.get("classname") == "info_player_start"]
    sp = [float(v) for v in starts[cfg["spawn_at"]]["origin"].split()]
    sp_yaw = float(starts[cfg["spawn_at"]].get("angles", "0 0 0").split()[1])
    y_off = (sp[2] - 1.0) * S
    boxes, slabbed, dropped = [], 0, 0
    for i in sorted(bsp.model_brushes(0)):
        contents = bsp.brushes[i][2]
        names = docboxes.brush_material_names(bsp, i)
        pick = ("water", None) if contents & WATER else material_for(cfg, names)
        if pick is None:
            dropped += 1
            continue
        mat, colour = pick
        parts, cut = brush_boxes(bsp, i, cfg.get("slab"))
        slabbed += cut
        if cut == 2:
            b = ramp_document_box(parts[0], mat, colour, y_off)
            region = cfg.get("region", ((-1e9, 1e9),) * 3)
            if all(region[k][0] <= b["at"][k] <= region[k][1] for k in range(3)) and mat != "water":
                boxes.append(b)
            continue
        for (u0, u1), (v0, v1), (z0, z1), phi in parts:
            cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
            c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
            x, y = cu * c - cv * s, cu * s + cv * c         # back out of the turned frame
            size = [(u1 - u0) * S, (z1 - z0) * S, (v1 - v0) * S]
            if mat == "water":
                phi = 0.0                                     # a liquid is axis-aligned
            if max(size) < cfg.get("min_size", MIN_SIDE) or min(size) <= 0:
                continue
            at = [round(x * S, 3), round(((z0 + z1) / 2) * S - y_off, 3), round(-y * S, 3)]
            region = cfg.get("region", ((-1e9, 1e9),) * 3)
            if any(not (region[k][0] <= at[k] <= region[k][1]) for k in range(3)):
                continue                                      # outside the playable region
            b = {"at": at,
                 "size": [round(v, 3) for v in size], "material": mat}
            if colour:
                b["colour"] = colour
            if phi:
                b["turn"] = [0, 1, 0, round(phi, 2)]
            boxes.append(b)
    for r in cfg.get("ramps", []):
        xs, zs, ys = r["x"], r["z"], r["y"]
        rb = (xs[0] / S, xs[1] / S, -zs[1] / S, -zs[0] / S, (ys[0] + y_off) / S, (ys[1] + y_off) / S,
              (ys[0] - 0.4 + y_off) / S, math.degrees(math.atan((ys[1] - ys[0]) / (xs[1] - xs[0]))), "x", 1)
        boxes.append(ramp_document_box(rb, "concrete", "#b9b4aa", y_off))
    boxes = [snap(b) for b in boxes]
    doc = {
        "format": 1, "kind": "playground_map", "id": cfg["id"], "name": cfg["name"],
        "blurb": cfg["blurb"], "map_kind": "sandbox", "tier": 1, "author": cfg["author"],
        "attribution": ("Geometry converted from %s by %s. The author's textures are not carried: "
                        "surfaces use this game's materials over Kenney's Prototype Textures (CC0). "
                        "Removed on request." % (cfg["source"], cfg["author"])),
        "spawn": [round(sp[0] * S, 3), 1.0, round(-sp[1] * S, 3)],
        "spawn_yaw": round(sp_yaw - 90.0, 1),
        "boxes": boxes, "declared": cfg.get("declared", []),
    }
    print("%s: %d boxes (%d brushes cut into slabs, %d tool brushes dropped)" % (cfg["id"], len(boxes), slabbed, dropped))
    return doc


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    doc = build(args[0], args[1])
    out = next((a[6:] for a in argv if a.startswith("--out=")), os.path.join(HERE, "..", "maps", doc["id"] + ".json"))
    with open(out, "w") as f:
        f.write(json.dumps(doc, indent=1) + "\n")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
