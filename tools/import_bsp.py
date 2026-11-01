#!/usr/bin/env python3
"""Converts a Source 1 community sandbox .bsp (VBSP 19/20) into a game-playground map document.

    tools/import_bsp.py <map.bsp> <config-name> [--out=maps/<id>.json]

`CONFIGS` below says, per map, its id, name, author, page, how its author's textures become the
game's materials, where the spawn is and what is dropped. The reader (bsp_read.py) and the material
naming and majority pick (dotbsp.docboxes) and the brush-to-box cutting (dotbsp.boxes.decompose with
tilt=True) are dot-map's shared ones; this file keeps only the document format, the GAME_MATERIAL table
and the per-map configs. Re-importing gm_smallbase gives a byte-identical document.

What it does, and why each choice:

- A document has boxes and no meshes, so each world brush becomes a BOX: its convex hull is
  found (bsp_read.Bsp.brush_hull) and, when every corner is a box corner, that box is written;
  a box turned about the vertical axis keeps its turn; a prism of any plan is the smallest
  turned rectangle round it; anything else (a slope, a stair) is cut into slabs along its longer
  horizontal axis, each as tall as the brush is at the slab's middle, so a ramp becomes a flight
  of 0.5 m risers, which a player climbs (the game's climb limit is 1.035 m).
- Axes: Source is Z-up, godot is (x, z, -y). Scale: 1 unit = 0.01905 m, the family's.
- Textures are NOT carried. A brush's surface comes from dot-map's shared list
  (dot-map-convert/dotbsp/source_textures.tsv, a new texture goes there and `bsp.py unmapped <bsp>` lists
  what it misses); GAME_MATERIAL turns the list's generic ids into this game's materials and
  tints, drawn over Kenney's CC0 Prototype Textures grid like every other map.
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
import bsp_read  # noqa: E402  (also puts dot-map-convert on sys.path)
from dotbsp import boxes as boxes_lib, docboxes, texturemap  # noqa: E402  (the passes and the texture list the map repositories share)

S = 0.01905
SLAB = 28.0     # source units: ~0.53 m, a slope's riser
MIN_SIDE = 0.04  # metres: a brush thinner than this in every direction is a bevel sliver, not a wall


def brush_boxes(bsp, index, slab=None):
    """dot-map's boxes.decompose for one brush: ([(u range), (v range), (z range), phi], cut), cut 0 for a
    box, 1 for slabs and 2 for a tilted ramp, whose box is then boxes.decompose's own ramp tuple."""
    planes = [bsp.planes[s[0]][:4] for s in bsp.brushsides[bsp.brushes[index][0]:][:bsp.brushes[index][1]] if not s[3]]
    parts = boxes_lib.decompose(planes, bsp.brush_hull(index), slab=slab or SLAB, tilt=True)
    if not parts:
        return [], 0
    if parts[0]["kind"] == "ramp":
        (x0, x1), (y0, y1), _z = parts[0]["x"], parts[0]["y"], parts[0]["z"]
        axis, zlow, zhigh, base, ang, sign = parts[0]["ramp"]
        return [(x0, x1, y0, y1, zlow, zhigh, base, ang, axis, sign)], 2
    out = [(p["x"], p["y"], p["z"], p["phi"]) for p in parts]
    return out, 1 if parts[0]["kind"] == "slab" else 0


# What the shared list's generic ids become here: (this game's material, colour or None). The game has no
# brick, plaster, tile or ceiling material (its surfaces are physical: concrete, rock, wood...), so the look
# is Kenney's grid under a tint, the tints the maps carried before the list (a brick wall is rock under
# #b0705a). The list's own tints are not used: they say what the mapper meant, these say what reads here.
# Anything not named is already one of the game's ids (concrete, metal, glass, grass, water) and passes through.
GAME_MATERIAL = {
    "brick_red": ("rock", "#b0705a"), "stone_wall": ("rock", None),
    "plaster_painted": ("concrete", "#d9d2c3"), "plaster_worn": ("concrete", "#d9d2c3"), "wallpaper": ("concrete", "#d9d2c3"),
    "ceiling": ("concrete", "#8d8b86"),
    "wood_planks": ("wood", None), "door_wood": ("wood", None), "wood_floor": ("wood", None), "parquet": ("wood", None),
    "roof_tiles": ("concrete", None), "tile_floor": ("concrete", None), "carpet": ("concrete", None), "flat": ("concrete", None),
    "mud": ("mud", None), "snow": ("snow", None),
}

# Per map. "overrides" is (substring of the classified texture name, material, colour or None), first match
# wins and is tried before the shared list: only what the list cannot say, and each entry needs a reason.
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
        # The list maps REFLECTIVITY (a developer pattern) to nothing a player reads; this map's grey
        # panels are drawn as a cool concrete. The source BSP is no longer on disk, so this entry
        # could not be re-checked against a re-import.
        "overrides": [("REFLECTIVITY", "concrete", "#a9aaae")],
    },
    "smallbase": {
        "id": "pgc_smallbase",
        "name": "Small Base",
        "blurb": "A small, lag-free concrete base for building and wiring: a brick-walled yard with a second storey, a grass patch and a small pool.",
        "author": "Rouglead",
        "source": "gm_smallbase, https://gamebanana.com/mods/60684",
        "spawn_at": 0,
        # The tops of the brick walls, which no player is meant to stand on.
        "declared": [
            {"min": [-12.4, 5.0, -12.4], "max": [12.4, 5.4, 12.4], "why": "tops of the upper brick walls"},
        ],
    },
}

WATER = 0x20


TEXTURE_MAP = texturemap.load()


def material_for(cfg, names):
    # The majority pick (sorted, so a tie follows the name, not the hash seed) is dot-map's. The map's own
    # overrides are tried first; then the shared list, whose generic id the game turns into its own.
    pick = docboxes.majority_material(names, cfg.get("overrides", []), None)
    if pick is not None or not [n for n in names if not n.startswith("TOOLS/")]:
        return pick
    hit = docboxes.majority_material(names, TEXTURE_MAP, ("", None))
    if not hit[0]:
        return ("concrete", None)             # a texture the list does not map, or maps to nothing
    mat, colour = GAME_MATERIAL.get(hit[0], (hit[0], None))
    return (mat, colour)


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
    # Garry's Mod maps use gmod_player_start where the others use info_player_start.
    starts = [e for e in bsp.entities if e.get("classname") in ("info_player_start", "gmod_player_start")]
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
