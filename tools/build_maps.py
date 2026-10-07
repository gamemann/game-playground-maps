#!/usr/bin/env python3
"""Writes every map document in maps/. Edit this, run it, commit both.

    python3 tools/build_maps.py          # write maps/*.json
    python3 tools/build_maps.py --check  # fail if a committed file differs (CI)

A map is boxes (centre + full size, the PlaygroundGeometry.box convention), an optional
turn about the box's own centre, a spawn, and the areas the survey may find unreached.
game-playground's maps/pg_data.gd builds it and defines the format.

Ramps are placed from where their TOP surface starts and ends, then dropped along their own
normal by half their thickness, so the surface meets the ground at both ends exactly. A ramp
dropped vertically instead leaves a lip at the top, which over a step's height is a wall.
"""
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAPS = ROOT / "maps"
AUTHOR = "TMC"


def r(v):
    return round(v, 4)


def box(at, size, colour="floor", turn=None):
    b = {"at": [r(c) for c in at], "size": [r(c) for c in size], "colour": colour}
    if turn is not None:
        b["turn"] = [r(c) for c in turn]
    return b


def ramp_z(x, z_low, y_low, z_high, y_high, width, colour="ramp", thickness=0.5):
    """A walkable ramp along Z: its top surface runs from (z_low, y_low) to (z_high, y_high)."""
    run = z_high - z_low
    rise = y_high - y_low
    length = math.hypot(run, rise)
    a = math.atan2(rise, abs(run))
    # Rising toward +Z is a turn of -a about X; toward -Z, +a.
    theta = -a if run > 0 else a
    normal = (0.0, math.cos(theta), math.sin(theta))
    mid = (x, (y_low + y_high) / 2.0, (z_low + z_high) / 2.0)
    centre = tuple(mid[i] - normal[i] * thickness / 2.0 for i in range(3))
    return box(centre, (width, thickness, length), colour, (1, 0, 0, math.degrees(theta)))


def ramp_x(z, x_low, y_low, x_high, y_high, length, colour="ramp", thickness=0.5):
    """A walkable ramp along X: its top surface runs from (x_low, y_low) to (x_high, y_high)."""
    run = x_high - x_low
    rise = y_high - y_low
    span = math.hypot(run, rise)
    a = math.atan2(rise, abs(run))
    # Rising toward +X is a turn of +a about Z; toward -X, -a.
    theta = a if run > 0 else -a
    normal = (-math.sin(theta), math.cos(theta), 0.0)
    mid = ((x_low + x_high) / 2.0, (y_low + y_high) / 2.0, z)
    centre = tuple(mid[i] - normal[i] * thickness / 2.0 for i in range(3))
    return box(centre, (span, thickness, length), colour, (0, 0, 1, math.degrees(theta)))


def walls(size, height, top_y=0.0, colour="platform"):
    half = size / 2.0
    out = []
    for side in (-1, 1):
        out.append(box((side * (half - 0.5), top_y + height / 2.0, 0), (1, height, size), colour))
        out.append(box((0, top_y + height / 2.0, side * (half - 0.5)), (size, height, 1), colour))
    return out


def wall_tops(size, top_y, why):
    half = size / 2.0
    return [
        {"min": [-half, top_y, -half], "max": [half, top_y + 0.5, -half + 1], "why": why},
        {"min": [-half, top_y, half - 1], "max": [half, top_y + 0.5, half], "why": why},
        {"min": [-half, top_y, -half], "max": [-half + 1, top_y + 0.5, half], "why": why},
        {"min": [half - 1, top_y, -half], "max": [half, top_y + 0.5, half], "why": why},
    ]


def doc(id_, name, blurb, spawn, spawn_yaw, boxes, declared, tier=1, props=None, wires=None):
    d = {
        "format": 1, "kind": "playground_map", "id": id_, "name": name, "blurb": blurb,
        "map_kind": "sandbox", "tier": tier, "author": AUTHOR,
        "spawn": [r(c) for c in spawn], "spawn_yaw": spawn_yaw,
        "boxes": boxes, "declared": declared,
    }
    if props:
        d["props"] = props
    if wires:
        d["wires"] = wires
    return d


# --- Props ---------------------------------------------------------------------------------
#
# A map's props are catalogue ids game-playground puts down when the map loads (pg_data.gd's
# `props`). `at` is the body's centre, so a prop standing on a floor at y is at y + half its
# height. Frozen unless loose=True: furniture that falls over on load is not furniture.

HALF_HEIGHT = {
    "plank": 0.075, "beam": 0.2, "panel": 0.05, "slab": 0.3, "pillar": 2.0, "platform": 0.2,
    "crate": 0.5, "crate_large": 1.0, "barrel": 0.7, "can": 0.25, "ball": 0.5,
    "beach_ball": 1.2, "boulder": 1.5, "die": 0.4, "button": 0.3, "lever": 0.45, "door": 1.3,
    "buggy": 0.9,
}


def prop(id_, x, floor_y, z, yaw=0.0, loose=False, tint=None, scale=None, physics=None, lift=0.0):
    """A prop standing on a floor at floor_y (lift raises it, for a button on a wall)."""
    p = {"id": id_, "at": [r(x), r(floor_y + HALF_HEIGHT.get(id_, 0.5) * (scale or 1.0) + lift), r(z)]}
    if yaw:
        p["yaw"] = r(yaw)
    if loose:
        p["frozen"] = False
    if tint:
        p["tint"] = tint
    if scale:
        p["scale"] = scale
    if physics:
        p["physics"] = physics
    return p


def wire(frm, out, to, in_):
    return {"from": frm, "out": out, "to": to, "in": in_}


# --- Geometry beyond axis-aligned ramps ------------------------------------------------------

def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _rotate(q, v):
    x, y, z, w = q
    p = _qmul(_qmul(q, (v[0], v[1], v[2], 0.0)), (-x, -y, -z, w))
    return p[:3]


def _turn_of(q):
    x, y, z, w = q
    w = max(-1.0, min(1.0, w))
    angle = 2.0 * math.acos(w)
    sin_half = math.sqrt(max(0.0, 1.0 - w * w))
    if sin_half < 1e-6:
        return None
    return (x / sin_half, y / sin_half, z / sin_half, math.degrees(angle))


def bridge(p0, p1, width, colour="ramp", thickness=0.5):
    """A slab whose TOP surface runs along the line p0 -> p1 in any direction: a sloped bridge
    or ramp. Yawed to the line, then pitched, then dropped along its own normal by half its
    thickness, so its surface passes through both points exactly (ramp_z's rule)."""
    dx, dy, dz = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    flat = math.hypot(dx, dz)
    length = math.hypot(flat, dy)
    yaw = math.atan2(dx, dz)
    pitch = -math.atan2(dy, flat)
    q = _qmul((0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)), (math.sin(pitch / 2), 0.0, 0.0, math.cos(pitch / 2)))
    normal = _rotate(q, (0.0, 1.0, 0.0))
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2)
    centre = tuple(mid[i] - normal[i] * thickness / 2.0 for i in range(3))
    return box(centre, (width, thickness, length), colour, _turn_of(q))


def building(cx, cz, w, d, h, door_side, colour, wall=0.4, door_w=2.4, door_h=2.8, roof=True):
    """Four walls with a doorway in one ("s" -Z, "n" +Z, "w" -X, "e" +X), a lintel over it and
    a flat roof at h. Returns (boxes, door_centre (x, z), door_yaw, inward (dx, dz))."""
    out = []
    y = h / 2.0
    hw, hd = w / 2.0, d / 2.0
    sides = {
        "s": ((cx, cz - hd + wall / 2), "x", w, (0, 1)),
        "n": ((cx, cz + hd - wall / 2), "x", w, (0, -1)),
        "w": ((cx - hw + wall / 2, cz), "z", d, (1, 0)),
        "e": ((cx + hw - wall / 2, cz), "z", d, (-1, 0)),
    }
    door = None
    for name, (centre, along, span, inward) in sides.items():
        if name != door_side:
            size = (span, h, wall) if along == "x" else (wall, h, span)
            out.append(box((centre[0], y, centre[1]), size, colour))
            continue
        piece = (span - door_w) / 2.0
        for side in (-1, 1):
            off = side * (door_w / 2.0 + piece / 2.0)
            if along == "x":
                out.append(box((centre[0] + off, y, centre[1]), (piece, h, wall), colour))
            else:
                out.append(box((centre[0], y, centre[1] + off), (wall, h, piece), colour))
        lintel_h = h - door_h
        ly = door_h + lintel_h / 2.0
        out.append(box((centre[0], ly, centre[1]), (door_w, lintel_h, wall) if along == "x" else (wall, lintel_h, door_w), colour))
        door = (centre, 0.0 if along == "x" else 90.0, inward)
    if roof:
        out.append(box((cx, h + 0.15, cz), (w, 0.3, d), "platform"))
    return out, door[0], door[1], door[2]


# --- Build Plots ---------------------------------------------------------------------------

PLOT_COLOURS = ["#3b6ea5", "#a55b3b", "#5f9e4f", "#8d5fa8", "#c2a23a", "#3f9a96", "#b04f72", "#6d7480"]


def plots():
    size, wall_h = 160.0, 6.0
    boxes = [box((0, -0.5, 0), (size, 1, size))]
    boxes += walls(size, wall_h)
    # The spawn plaza in the middle, and eight plots round it on a 40 m pitch: 26 m of pad
    # each, 14 m of path between. A pad is 0.2 m: a step, not a climb.
    boxes.append(box((0, 0.1, 0), (20, 0.2, 20), "start"))
    n = 0
    for gx in (-1, 0, 1):
        for gz in (-1, 0, 1):
            if gx == 0 and gz == 0:
                continue
            cx, cz = gx * 40.0, gz * 40.0
            boxes.append(box((cx, 0.1, cz), (26, 0.2, 26), PLOT_COLOURS[n]))
            # The claim pad: on the path, on the plot's side nearest the plaza.
            dx, dz = -gx, -gz
            if dx != 0 and dz != 0:
                dz = 0
            boxes.append(box((cx + dx * 14.5, 0.05, cz + dz * 14.5), (2, 0.1, 2), "boost"))
            n += 1
    # A viewing deck in the north-west corner, 4 m up, and a 20-degree ramp onto it.
    boxes.append(box((-66, 3.75, -66), (10, 0.5, 10), "platform"))
    boxes.append(ramp_z(-66, -50.0, 0.0, -61.0, 4.0, 6))
    declared = wall_tops(size, wall_h, "the tops of the walls, 6 m up: they keep props in")
    # A tree where the paths cross, and lamps on the plaza's corners.
    for tx in (-20, 20):
        for tz in (-20, 20):
            b, dcl = tree(tx, tz)
            boxes += b
            declared += dcl
    for lx in (-11, 11):
        for lz in (-11, 11):
            b, dcl = lamp(lx, lz, 0.2)
            boxes += b
            declared += dcl
    # A supply depot on the plaza's east side, loose, to start building with before anybody
    # opens the menu; and a buggy parked by the deck for getting round the plots.
    props = []
    for k in range(6):
        props.append(prop("plank", 7.0, 0.2 + k * 0.15, -4.0, yaw=90.0, loose=True))
    for k in range(3):
        props.append(prop("panel", 7.0, 0.2 + k * 0.1, 3.5, loose=True))
    for k in range(4):
        props.append(prop("crate", 8.5, 0.2 + (k // 2), -0.6 + (k % 2) * 1.05, loose=True))
    props.append(prop("barrel", 5.5, 0.2, 0.0, loose=True))
    props.append(prop("buggy", -66.0, 0.0, -25.0, loose=True))
    return doc("pgc_plots", "Build Plots",
               "Eight plots round a spawn plaza, a claim pad in front of each, a depot of planks and crates to start with, and a deck to look down on them from.",
               (0, 1, 0), 0.0, boxes, declared, props=props)


# --- Quarry --------------------------------------------------------------------------------

def quarry():
    boxes, declared = [], []
    floor_y, b_y = -12.0, -6.0
    boxes.append(box((0, floor_y - 0.5, 0), (140, 1, 140), "#5a4e42"))
    # The rim (top y 0), a frame from 50 to 70 out.
    rim = "#8a7a62"
    boxes.append(box((0, -6, 60), (140, 12, 20), rim))
    boxes.append(box((0, -6, -60), (140, 12, 20), rim))
    boxes.append(box((60, -6, 0), (20, 12, 100), rim))
    boxes.append(box((-60, -6, 0), (20, 12, 100), rim))
    # The terrace (top y -6), a frame from 30 to 50 out.
    terrace = "#73654f"
    boxes.append(box((0, -9, 40), (100, 6, 20), terrace))
    boxes.append(box((0, -9, -40), (100, 6, 20), terrace))
    boxes.append(box((40, -9, 0), (20, 6, 60), terrace))
    boxes.append(box((-40, -9, 0), (20, 6, 60), terrace))
    # A 3 m wall round the rim's outer edge, so a thrown prop stays in the quarry.
    boxes += walls(140, 3.0, 0.0, "#5e5547")
    declared += wall_tops(140, 3.0, "the tops of the rim's walls, 3 m up")
    # Ramps down, one per level per side, offset so the way down is a walk round.
    boxes.append(ramp_z(-20, 30.0, b_y, 50.0, 0.0, 6))
    boxes.append(ramp_z(20, 10.0, floor_y, 30.0, b_y, 6))
    boxes.append(ramp_z(20, -30.0, b_y, -50.0, 0.0, 6))
    boxes.append(ramp_z(-20, -10.0, floor_y, -30.0, b_y, 6))
    # Rails: a line across the pit floor and one along the north terrace. 0.15 m: a step.
    rail = "#9aa0a6"
    for z in (-0.7, 0.7):
        boxes.append(box((0, floor_y + 0.075, z), (56, 0.15, 0.2), rail))
    for z in (39.3, 40.7):
        boxes.append(box((8, b_y + 0.075, z), (80, 0.15, 0.2), rail))
    # A cart on the pit rails, 1.0 m above the floor: a climb, just.
    boxes.append(box((-8, floor_y + 0.15 + 0.425, 0), (2.0, 0.85, 1.2), "#7a4a2a"))
    # Ore piles, climbable, and two boulders nobody climbs.
    for at in ((12, -16), (-14, 14), (18, 12)):
        boxes.append(box((at[0], floor_y + 0.45, at[1]), (2.4, 0.9, 2.4), "#6b6f4e"))
    for at in ((-18, -18), (22, -20)):
        boxes.append(box((at[0], floor_y + 1.25, at[1]), (3, 2.5, 3), "#5c5c5c"))
        declared.append({"min": [at[0] - 1.5, floor_y + 2.5, at[1] - 1.5],
                         "max": [at[0] + 1.5, floor_y + 3.0, at[1] + 1.5],
                         "why": "a boulder's top, 2.5 m up: a climb nobody makes"})
    props, wires = [], []
    # A blasting hut on the west terrace: a lever outside opens its door, and inside are the
    # barrels (with pg_destruction on, a shot one goes up and takes its neighbours with it).
    hut, door_at, door_yaw, inward = building(-40.0, 0.0, 10.0, 8.0, 4.0, "e", "#7b5a3a")
    for b in hut:
        b["at"][1] = r(b["at"][1] + b_y)
    boxes += hut
    n = len(props)
    props.append(prop("door", door_at[0], b_y, door_at[1], yaw=door_yaw))
    props.append(prop("lever", door_at[0] + 0.6, b_y, door_at[1] + 2.0))
    wires.append(wire(n + 1, "switched", n, "toggle"))
    for k in range(6):
        props.append(prop("barrel", -42.5 + (k % 3) * 1.15, b_y, -1.5 + (k // 3) * 1.15, loose=True))
    # Barrels in two clusters on the pit floor, ore crates by the cart, boulders on the north
    # rim one push from the edge, and a buggy by the spawn.
    for cx_, cz_ in ((6, -20), (-22, 6)):
        for k in range(4):
            props.append(prop("barrel", cx_ + (k % 2) * 1.1, floor_y, cz_ + (k // 2) * 1.1, loose=True))
    for k in range(5):
        props.append(prop("crate", -12.0 + (k % 3) * 1.05, floor_y + (k // 3), 3.0, loose=True, tint="#6b6f4e"))
    for bx in (-12.0, 4.0, 18.0):
        props.append(prop("boulder", bx, 0.0, 52.0, loose=True))
    props.append(prop("buggy", 12.0, 0.0, 60.0, loose=True))
    return doc("pgc_quarry", "Quarry",
               "A pit in two terraces with ramps between them, rails and a cart, boulders on the rim, barrels to blow up, and a blasting hut with a lever on its door.",
               (0, 1, 60), 0.0, boxes, declared, props=props, wires=wires)


# --- Slide Hill ----------------------------------------------------------------------------

def slopes():
    size, wall_h = 180.0, 6.0
    boxes = [box((0, -0.5, 0), (size, 1, size))]
    boxes += walls(size, wall_h)
    boxes.append(box((0, 0.1, 80), (12, 0.2, 12), "start"))
    # The hill: a long 14-degree walk up from the spawn side to a deck 20 m up, and a
    # 24-degree slope down the far side. Measured (2026-10-07): at the catalogue's friction
    # (1.0) a plank or crate set on the slope settles and stays, so it can be built on; with
    # its friction at 0.2 (the tool gun's Edit properties or Physical properties) it slides
    # about 35 m to the bottom, and prop surfing carries whoever stands on it.
    top = 20.0
    boxes.append(ramp_z(0, 70.0, 0.0, -10.0, top, 30))
    boxes.append(box((0, top - 0.25, -20), (30, 0.5, 20), "platform"))
    boxes.append(ramp_z(0, -75.0, 0.0, -30.0, top, 30, "#5f9e4f"))
    # The pen on the deck: a 1 m wall round an 8 m square, the "stand in the box" spot to be
    # picked up and thrown from. 1.0 m is under the 1.035 m a jump climbs, so nobody is shut in.
    pen = "boost"
    for side in (-1, 1):
        boxes.append(box((side * 4.15, top + 0.5, -20), (0.3, 1.0, 8.6), pen))
        boxes.append(box((0, top + 0.5, -20 + side * 4.15), (8.0, 1.0, 0.3), pen))
    # A halfpipe along Z on the east side: two 31-degree faces 14 m apart, each topped by a
    # 5 m ledge, for riding a prop back and forth or dropping in on one.
    lip = 6.0
    boxes.append(ramp_x(0, 48.0, 0.0, 38.0, lip, 60))
    boxes.append(ramp_x(0, 62.0, 0.0, 72.0, lip, 60))
    boxes.append(box((35.5, lip / 2.0, 0), (5, lip, 60), "platform"))
    boxes.append(box((74.5, lip / 2.0, 0), (5, lip, 60), "platform"))
    declared = wall_tops(size, wall_h, "the tops of the walls, 6 m up: they keep props in")
    props = []
    # Sleds at the head of the far slope: planks with their friction at 0.05, on the flat deck
    # so they wait to be pushed over the edge. Stand on one first.
    for sx_ in (-10.0, -6.0, 6.0, 10.0):
        props.append(prop("plank", sx_, top, -27.5, loose=True, tint="#e0a052", physics={"gravity": True, "weight": 1.0, "friction": 0.05, "bounce": 0.0}))
    # Crates on the hill (friction 1.0 holds them on 14 degrees), balls in the halfpipe, and a
    # buggy at the foot of the hill.
    for at in ((-8, 40), (6, 25), (-4, 10)):
        y = top * (70.0 - at[1]) / 80.0
        props.append(prop("crate", at[0], y + 0.1, at[1], loose=True))
    for z in (-15.0, 0.0, 15.0):
        props.append(prop("beach_ball", 55.0, 0.0, z, loose=True))
    props.append(prop("buggy", 25.0, 0.0, 75.0, loose=True))
    return doc("pgc_slopes", "Slide Hill",
               "A hill to a deck 20 m up with a pen on top to be thrown from, sleds waiting at the head of a far slope, and a halfpipe.",
               (0, 1, 80), 0.0, boxes, declared, props=props)


def tree(x, z, floor_y=0.0, height=3.0, canopy=3.2):
    """A trunk and a block of leaves. The leaves' top is somewhere nobody walks to."""
    boxes = [box((x, floor_y + height / 2.0, z), (0.6, height, 0.6), "#6b4a2a"),
             box((x, floor_y + height + canopy * 0.4, z), (canopy, canopy * 0.8, canopy), "#3e7a3a")]
    top = floor_y + height + canopy * 0.8
    declared = [{"min": [r(x - canopy / 2), r(top - 0.2), r(z - canopy / 2)],
                 "max": [r(x + canopy / 2), r(top + 0.5), r(z + canopy / 2)], "why": "a tree's leaves"}]
    return boxes, declared


def lamp(x, z, floor_y=0.0):
    """A 4.5 m post with a lamp head 4.7 m up. Returns (boxes, declared)."""
    return ([box((x, floor_y + 2.25, z), (0.25, 4.5, 0.25), "#3a3d42"),
             box((x, floor_y + 4.6, z), (0.5, 0.2, 0.5), "#e8d9a0")],
            [{"min": [r(x - 0.25), r(floor_y + 4.5), r(z - 0.25)], "max": [r(x + 0.25), r(floor_y + 5.2), r(z + 0.25)],
              "why": "a lamp's head"}])


# --- Town ----------------------------------------------------------------------------------

ROAD = "#3a3d42"
KERB = "#8c8f94"


def town():
    size, wall_h = 200.0, 8.0
    boxes = [box((0, -0.5, 0), (size, 1, size), "#4f6b45")]
    boxes += walls(size, wall_h, colour="#6d7480")
    declared = wall_tops(size, wall_h, "the town's outer walls, 8 m up")
    props, wires = [], []

    # Two roads crossing in the middle, 14 m wide, with a 0.15 m pavement (a step) either side.
    for along in ("x", "z"):
        if along == "x":
            boxes.append(box((0, 0.01, 0), (size - 2, 0.02, 14), ROAD))
        else:
            # A hair higher than the other road, so the crossing is one surface and not two
            # fighting for the same depth.
            boxes.append(box((0, 0.0125, 0), (14, 0.025, size - 2), ROAD))
    # The plaza on the north-east block: a fountain (a 0.5 m ring, a 2.5 m column), benches.
    px, pz = 45.0, 45.0
    boxes.append(box((px, 0.075, pz), (70, 0.15, 70), KERB))
    for side in (-1, 1):
        boxes.append(box((px + side * 4.75, 0.4, pz), (0.5, 0.5, 10), "#9aa3ad"))
        boxes.append(box((px, 0.4, pz + side * 4.75), (9, 0.5, 0.5), "#9aa3ad"))
    boxes.append(box((px, 1.4, pz), (1.2, 2.5, 1.2), "#9aa3ad"))
    declared.append({"min": [px - 0.6, 2.5, pz - 0.6], "max": [px + 0.6, 3.0, pz + 0.6],
                     "why": "the top of the fountain's column, 2.5 m up"})
    for at in ((px - 14, pz - 14), (px + 14, pz - 14), (px - 14, pz + 14), (px + 14, pz + 14)):
        boxes.append(box((at[0], 0.4, at[1]), (3, 0.5, 0.8), "#7b5a3a"))
    for i, at in enumerate(((px - 6, pz - 9), (px + 7, pz + 9), (px + 9, pz - 6))):
        props.append(prop("beach_ball", at[0], 0.15, at[1], loose=True))
    # Trees round the plaza's edge, and a stage on its far side: 0.9 m, up two 0.45 m steps
    # on each end. (0.45 is over a walk's 0.4 step, so it is a hop, which a stage is.)
    for i in range(6):
        for at in ((px - 30 + i * 12, pz - 30), (px - 30 + i * 12, pz + 30)):
            b, dcl = tree(at[0], at[1], 0.15)
            boxes += b
            declared += dcl
    sx_, sz_ = px, pz + 22
    boxes.append(box((sx_, 0.15 + 0.45, sz_), (16, 0.9, 6), "#7b5a3a"))
    for side in (-1, 1):
        boxes.append(box((sx_ + side * 9.0, 0.15 + 0.225, sz_), (2, 0.45, 4), "#7b5a3a"))
    # Market stalls along the west of the plaza: a counter and its goods, loose.
    for i in range(3):
        mz = pz - 14 + i * 12
        boxes.append(box((px - 24, 0.15 + 0.5, mz), (2, 1.0, 5), "#a55b3b"))
        props.append(prop("crate", px - 24, 1.15, mz - 1.5, loose=True))
        props.append(prop("can", px - 24, 1.15, mz, loose=True))
        props.append(prop("die", px - 24, 1.15, mz + 1.5, loose=True))
    # Street trees and lamps down both roads, on the verges.
    for k in range(-4, 5):
        if k == 0:
            continue
        t = k * 20.0
        for side in (-1, 1):
            if not (t > 8 and side > 0):
                b, dcl = tree(t, side * 11.0)
                boxes += b
                declared += dcl
            if abs(t + 10.0) < 95:
                b, dcl = lamp(side * 9.0, t + 10.0)
                boxes += b
                declared += dcl

    # Buildings: each enterable through a door wired to a button outside and inside, and a
    # ramp up the outside to its roof. (block centre, size, height, door side, colour)
    houses = [
        ((-45, 30), (22, 16), 6.0, "s", "#a55b3b"),
        ((-45, 65), (18, 14), 9.0, "e", "#c2a23a"),
        ((-30, -45), (26, 18), 7.0, "n", "#3b6ea5"),
        ((-65, -45), (14, 22), 5.0, "e", "#5f9e4f"),
        ((40, -40), (30, 20), 6.0, "w", "#8d5fa8"),
    ]
    for (cx, cz), (w, d), h, door_side, colour in houses:
        boxes.append(box((cx, 0.075, cz), (w + 8, 0.15, d + 8), KERB))
        built, door_at, door_yaw, inward = building(cx, cz, w, d, h, door_side, colour)
        for b in built:
            # Up onto the pavement: every wall stands on it.
            b["at"][1] = r(b["at"][1] + 0.15)
        boxes += built
        # The roof ramp, along the side wall away from the north-south road, rising toward the
        # road so its foot is out past the far side; it ends on a post touching the wall, whose
        # top is level with the roof (no gap: a gap beside a wall is a slot).
        sx = 1.0 if cx > 0 else -1.0
        sz = 1.0 if cz > 0 else -1.0
        roof_top = h + 0.45
        rx = cx + sx * (w / 2.0 + 1.8)
        top_z = cz - sz * (d / 2.0 - 3.0)
        run = max(roof_top * 1.9, d - 3.0 + 4.5)
        boxes.append(ramp_z(rx, top_z + sz * run, 0.0, top_z, roof_top, 3.6))
        boxes.append(box((rx, roof_top / 2.0, top_z - sz * 1.5), (3.6, roof_top, 3.0), colour))
        # The door in its doorway, a button either side of it 1.6 m along the wall.
        n = len(props)
        props.append(prop("door", door_at[0], 0.15, door_at[1], yaw=door_yaw))
        along = (1, 0) if door_yaw == 0.0 else (0, 1)
        out_x = door_at[0] - inward[0] * 0.33 + along[0] * 1.9
        out_z = door_at[1] - inward[1] * 0.33 + along[1] * 1.9
        in_x = door_at[0] + inward[0] * 0.33 - along[0] * 1.9
        in_z = door_at[1] + inward[1] * 0.33 - along[1] * 1.9
        props.append(prop("button", out_x, 0.15, out_z, yaw=door_yaw, lift=1.0))
        props.append(prop("button", in_x, 0.15, in_z, yaw=door_yaw, lift=1.0))
        wires.append(wire(n + 1, "pressed", n, "toggle"))
        wires.append(wire(n + 2, "pressed", n, "toggle"))
        # Something inside to find.
        props.append(prop("crate", cx + 2, 0.15, cz, loose=True))
        props.append(prop("crate", cx + 2, 1.15, cz, loose=True))
        props.append(prop("barrel", cx - 3, 0.15, cz + 2, loose=True))

    # A car park in the south-east block with two buggies.
    boxes.append(box((50, 0.03, -80), (40, 0.06, 16), "#2e3136"))
    for x in (40, 52):
        props.append(prop("buggy", x, 0.06, -80, loose=True))
    return doc("pgc_town", "Town",
               "Two roads, a fountain plaza, five buildings with doors on buttons and ramps to their roofs, and a car park.",
               (0, 1, 80), 0.0, boxes, declared, props=props, wires=wires)


# --- Sky Islands ---------------------------------------------------------------------------

ISLAND_COLOURS = ["#5f9e4f", "#4f8f7a", "#6f8f3f", "#8f8a4f", "#4f7a8f", "#8d5fa8"]


def _edge(c, d, half):
    """Where the line from an island's centre c along unit direction d leaves its square."""
    t = half / max(abs(d[0]), abs(d[1]))
    return (c[0] + d[0] * t, c[1] + d[1] * t)


def islands():
    size, wall_h = 240.0, 6.0
    boxes = [box((0, -0.5, 0), (size, 1, size), "#4f6b45")]
    boxes += walls(size, wall_h, colour="#6d7480")
    declared = wall_tops(size, wall_h, "the outer walls, 6 m up")
    props = []

    ring, half, thick = 55.0, 10.0, 3.0
    centres, tops = [], []
    for i in range(6):
        a = math.radians(i * 60.0)
        centres.append((ring * math.cos(a), ring * math.sin(a)))
        tops.append(8.0 + i * 5.0)
    for i, (c, top) in enumerate(zip(centres, tops)):
        boxes.append(box((c[0], top - thick / 2.0, c[1]), (2 * half, thick, 2 * half), ISLAND_COLOURS[i]))

    def link(i, j, width, colour):
        ci, cj = centres[i], centres[j]
        dx, dz = cj[0] - ci[0], cj[1] - ci[1]
        n = math.hypot(dx, dz)
        d = (dx / n, dz / n)
        a = _edge(ci, d, half)
        b = _edge(cj, (-d[0], -d[1]), half)
        return bridge((a[0], tops[i], a[1]), (b[0], tops[j], b[1]), width, colour)

    # Bridges up the ring, 5 m a step: a gentle walk, 4 m wide and no rails.
    for i in range(5):
        boxes.append(link(i, i + 1, 4.0, "ramp"))
    # And the slide: from the top island straight back down to the first, 25 m in 32, about
    # 38 degrees. Walkable, just; a prop with its friction turned down goes down it fast.
    boxes.append(link(5, 0, 6.0, "#c25b4a"))
    # From the ground up to the first island.
    c0 = centres[0]
    boxes.append(ramp_z(c0[0], c0[1] - half - 36.0, 0.0, c0[1] - half, tops[0], 5.0))

    # Things on the islands.
    c5, c2, c3 = centres[5], centres[2], centres[3]
    for k in range(3):
        props.append(prop("plank", c5[0] - 6 + k * 2.5, tops[5], c5[1] - 3, yaw=60.0, loose=True,
                          physics={"gravity": True, "weight": 1.0, "friction": 0.05, "bounce": 0.0}, tint="#e0a052"))
    # Two boulders at the head of the slide, one push from going down it.
    props.append(prop("boulder", c5[0] + 2.5, tops[5], c5[1] + 6.5, loose=True))
    props.append(prop("boulder", c5[0] + 7.0, tops[5], c5[1] + 3.0, loose=True))
    for k in range(4):
        props.append(prop("barrel", c2[0] - 3 + (k % 2) * 1.2, tops[2], c2[1] + (k // 2) * 1.2, loose=True))
    for k in range(3):
        for level in range(3 - k):
            props.append(prop("crate", c3[0] - 2 + k * 1.05 + level * 0.5, tops[3] + level * 1.0, c3[1], loose=True))
    for at in ((-20, 10), (15, -25), (-10, -40), (30, 30)):
        props.append(prop("beach_ball", at[0], 0.0, at[1], loose=True))
    return doc("pgc_islands", "Sky Islands",
               "Six islands climbing a ring on bridges, a slide from the top one back to the first, and nothing between you and the ground.",
               (c0[0], 1, c0[1] - half - 40.0), 180.0, boxes, declared, props=props)


# --- Construction Site ---------------------------------------------------------------------

CONCRETE = "#8a8a84"
DIRT = "#7a6548"


def site():
    size, wall_h = 180.0, 3.0
    boxes = [box((0, -0.5, 0), (size, 1, size), DIRT)]
    boxes += walls(size, wall_h, colour="#c2a23a")
    declared = wall_tops(size, wall_h, "the site fence, 3 m up")
    props, wires = [], []

    # The frame: a 30 x 20 m footprint, floors every 4.5 m, three of them open slabs on
    # 0.6 m columns, the top one open to the sky. Climbed by a switchback on the east side:
    # lane A (next to the frame) carries the first and third ramps, lane B the second, and a
    # landing at each floor spans both lanes and touches the slab's edge.
    fx, fz, fw, fd, storey = -25.0, -20.0, 30.0, 20.0, 4.5
    boxes.append(box((fx, 0.15, fz), (fw, 0.3, fd), CONCRETE))
    floors = [storey * k for k in (1, 2, 3)]
    for y in floors:
        boxes.append(box((fx, y - 0.15, fz), (fw, 0.3, fd), CONCRETE))
    for cx_ in (fx - fw / 2 + 0.3, fx, fx + fw / 2 - 0.3):
        for cz_ in (fz - fd / 2 + 0.3, fz + fd / 2 - 0.3):
            boxes.append(box((cx_, floors[-1] / 2.0, cz_), (0.6, floors[-1] - 0.3, 0.6), CONCRETE))
    east = fx + fw / 2.0
    lane_a, lane_b, lane_w = east + 1.8, east + 5.4, 3.6
    z0 = fz - fd / 2.0  # flush with the frame: 1 m in left a 0.4 m slot against the corner column
    run = storey * 1.8
    # Ramp 1 (lane A, rising +Z) to floor 1; landing 1; ramp 2 (lane B, rising -Z) to floor 2;
    # landing 2; ramp 3 (lane A, rising +Z, 9 m over ramp 1) to floor 3; landing 3.
    boxes.append(ramp_z(lane_a, z0, 0.0, z0 + run, floors[0], lane_w))
    boxes.append(box((east + 3.6, floors[0] - 0.15, z0 + run + 1.5), (7.2, 0.3, 3.0), CONCRETE))
    boxes.append(ramp_z(lane_b, z0 + run, floors[0], z0, floors[1], lane_w))
    boxes.append(box((east + 3.6, floors[1] - 0.15, z0 - 1.5), (7.2, 0.3, 3.0), CONCRETE))
    boxes.append(ramp_z(lane_a, z0, floors[1], z0 + run, floors[2], lane_w))
    boxes.append(box((east + 3.6, floors[2] - 0.15, z0 + run + 1.5), (7.2, 0.3, 3.0), CONCRETE))

    # The tower crane: a 2 m mast 28 m tall, and a jib along X over the frame.
    crane_x, crane_z, mast = 15.0, -38.0, 28.0
    boxes.append(box((crane_x, mast / 2.0, crane_z), (2, mast, 2), "#d4a017"))
    boxes.append(box((crane_x - 12.0, mast + 0.5, crane_z), (40, 1.0, 1.2), "#d4a017"))
    boxes.append(box((crane_x + 6.0, mast - 1.0, crane_z), (4, 2.0, 2.5), "#5a5d63"))
    declared.append({"min": [crane_x - 32.0, mast - 0.2, crane_z - 1.3], "max": [crane_x + 8.0, mast + 1.5, crane_z + 1.3],
                     "why": "the crane's jib and mast top, 28 m up"})

    # A dirt kicker for the buggies: up 2.5 m at 15 degrees, a 6 m table, and down again.
    kx, kz, mound = 40.0, 35.0, "#5e4a33"
    boxes.append(ramp_z(kx, kz - 18.0, 0.0, kz - 9.0, 2.5, 8.0, mound))
    boxes.append(box((kx, 1.25, kz - 6.0), (8.0, 2.5, 6.0), mound))
    boxes.append(ramp_z(kx, kz + 6.0, 0.0, kz - 3.0, 2.5, 8.0, mound))
    # A bumps track beside it: three mounds 1.2 m high, up and down at about 13 degrees.
    for k in range(3):
        bz = -10.0 + k * 14.0
        boxes.append(ramp_z(62.0, bz - 5.0, 0.0, bz, 1.2, 6.0, mound))
        boxes.append(ramp_z(62.0, bz + 5.0, 0.0, bz, 1.2, 6.0, mound))
    props.append(prop("buggy", kx - 10.0, 0.0, kz - 30.0, loose=True))
    props.append(prop("buggy", kx + 10.0, 0.0, kz - 30.0, loose=True))

    # The site office, a door on a button either side.
    office, door_at, door_yaw, inward = building(-50.0, 45.0, 12.0, 8.0, 3.5, "s", "#e8e2d0")
    boxes += office
    n = len(props)
    props.append(prop("door", door_at[0], 0.0, door_at[1], yaw=door_yaw))
    props.append(prop("button", door_at[0] + 1.9, 0.0, door_at[1] - inward[1] * 0.33, lift=1.0))
    props.append(prop("button", door_at[0] - 1.9, 0.0, door_at[1] + inward[1] * 0.33, lift=1.0))
    wires.append(wire(n + 1, "pressed", n, "toggle"))
    wires.append(wire(n + 2, "pressed", n, "toggle"))
    declared.append({"min": [-56.0, 3.5, 41.0], "max": [-44.0, 4.5, 49.0], "why": "the office roof, 3.65 m up"})
    for k in range(6):
        props.append(prop("can", -56.0 + k * 2.4, 0.0, 38.0, tint="#e0702a", loose=True))

    # Material piles, loose: everything a frame needs, stacked where a truck would drop it.
    for k in range(8):
        props.append(prop("plank", 5.0, k * 0.15, 10.0, loose=True))
    for k in range(4):
        props.append(prop("beam", 5.0, k * 0.4, 16.0, loose=True))
    for k in range(4):
        props.append(prop("panel", 14.0, k * 0.1, 12.0, loose=True))
    for k in range(2):
        props.append(prop("slab", 14.0, k * 0.6, 22.0, loose=True))
    for k in range(3):
        props.append(prop("pillar", 22.0 + k * 1.5, 0.0, 10.0))
    # And things already up on the frame, to throw off it.
    for k in range(3):
        props.append(prop("crate", fx - 8.0 + k * 1.1, floors[1], fz, loose=True))
    props.append(prop("barrel", fx + 6.0, floors[2], fz + 4.0, loose=True))
    return doc("pgc_site", "Construction Site",
               "A half-built three-storey frame climbed by switchback ramps, a tower crane, piles of planks and beams, a site office and a kicker for the buggies.",
               (0, 1, 60), 180.0, boxes, declared, props=props, wires=wires)


# --- Warehouse ---------------------------------------------------------------------------

def warehouse():
    size, wall_h = 160.0, 4.0
    boxes = [box((0, -0.5, 0), (size, 1, size), "#5a5d63")]
    boxes += walls(size, wall_h, colour="#6d7480")
    declared = wall_tops(size, wall_h, "the yard fence, 4 m up")
    props, wires = [], []

    # The hall: 80 x 50 m, its floor at dock height (1.2 m, a climb a jump does not make), walls
    # 12 m and a roof. South wall: two 8 m loading doorways 6 m high; the east one has a ramp
    # up from the yard, the west one is a sheer dock edge to drive off.
    hx, hz, hw, hd, hh, dock = 0.0, -20.0, 80.0, 50.0, 12.0, 1.2
    wall_c, wt = "#9c7134", 0.6
    boxes.append(box((hx, dock / 2.0, hz), (hw, dock, hd), "#7d8189"))
    south = hz + hd / 2.0
    top = dock + hh
    for side in (-1, 1):
        boxes.append(box((hx + side * (hw / 2 - wt / 2), dock + hh / 2, hz), (wt, hh, hd), wall_c))
    boxes.append(box((hx, dock + hh / 2, hz - hd / 2 + wt / 2), (hw, hh, wt), wall_c))
    # South wall in five pieces round the two doorways (centred at x -20 and +20, 8 m wide).
    door_xs, door_w, door_h = (-20.0, 20.0), 8.0, 6.0
    edges = [-hw / 2, door_xs[0] - door_w / 2, door_xs[0] + door_w / 2, door_xs[1] - door_w / 2, door_xs[1] + door_w / 2, hw / 2]
    for k in (0, 2, 4):
        a, b = edges[k], edges[k + 1]
        boxes.append(box(((a + b) / 2, dock + hh / 2, south - wt / 2), (b - a, hh, wt), wall_c))
    for dx in door_xs:
        boxes.append(box((dx, dock + door_h + (hh - door_h) / 2, south - wt / 2), (door_w, hh - door_h, wt), wall_c))
    boxes.append(box((hx, top + 0.2, hz), (hw, 0.4, hd), "#6f7480"))
    declared.append({"min": [-hw / 2, top, hz - hd / 2], "max": [hw / 2, top + 1.0, hz + hd / 2], "why": "the warehouse roof"})
    # The ramp up at the east doorway; the west one is the dock edge.
    boxes.append(ramp_z(door_xs[1], south + 6.0, 0.0, south, dock, door_w))

    # Racking: four rows of 30 m, 2 m deep, shelves at 2.5 and 5 m above the floor on posts
    # every 5 m, aisles of 6 m. The shelves are declared: nobody walks up a rack.
    rack_c, shelf_c = "#3b6ea5", "#c2a23a"
    for row, rz in enumerate((-36.0, -28.0, -20.0, -12.0)):
        for px_ in range(7):
            x = -25.0 + px_ * 5.0
            for dz in (-0.85, 0.85):
                boxes.append(box((x, dock + 2.75, rz + dz), (0.3, 5.5, 0.3), rack_c))
        for level in (2.5, 5.0):
            boxes.append(box((-10.0, dock + level, rz), (30.3, 0.2, 2.0), shelf_c))
            # Crates on the shelves, loose: a shelf is flat, and knocking them off is the point.
            for k in range(5):
                props.append(prop("crate", -22.0 + k * 6.0 + (row % 2) * 2.0, dock + level + 0.1, rz, loose=True))
        declared.append({"min": [-25.2, dock + 2.4, rz - 1.0], "max": [5.2, dock + 6.0, rz + 1.0], "why": "the rack shelves"})

    # A catwalk round the north and east walls, 6 m up and 2.5 m wide, reached by a ramp up the
    # west end of the north wall. Barrels along it to roll off.
    cw_y = dock + 6.0
    north = hz - hd / 2 + wt
    # From where the ramp tops out to the east wall: overlapping the ramp's end instead left
    # 1.4 m of headroom where the two met, and nobody got on.
    cw_start, cw_end = -hw / 2 + wt + 14.0, hw / 2 - wt
    boxes.append(box(((cw_start + cw_end) / 2, cw_y - 0.15, north + 1.25), (cw_end - cw_start, 0.3, 2.5), "#5a5d63"))
    boxes.append(box((hx + hw / 2 - wt - 1.25, cw_y - 0.15, hz - 5.0), (2.5, 0.3, hd - 10.0 - wt), "#5a5d63"))
    boxes.append(ramp_x(north + 1.25, -hw / 2 + wt, dock, -hw / 2 + wt + 14.0, cw_y, 2.5))
    for k in range(4):
        props.append(prop("barrel", 0.0 + k * 6.0, cw_y, north + 1.25, loose=True))

    # The office in the south-west corner of the hall, a door on a button.
    office, door_at, door_yaw, inward = building(-30.0, south - 8.0, 12.0, 8.0, 3.5, "e", "#e8e2d0")
    for b in office:
        b["at"][1] = r(b["at"][1] + dock)
    boxes += office
    n = len(props)
    props.append(prop("door", door_at[0], dock, door_at[1], yaw=door_yaw))
    props.append(prop("button", door_at[0] - inward[0] * 0.33, dock, door_at[1] + 1.9, yaw=door_yaw, lift=1.0))
    props.append(prop("button", door_at[0] + inward[0] * 0.33, dock, door_at[1] - 1.9, yaw=door_yaw, lift=1.0))
    wires.append(wire(n + 1, "pressed", n, "toggle"))
    wires.append(wire(n + 2, "pressed", n, "toggle"))
    declared.append({"min": [-36.0, dock + 3.5, south - 12.0], "max": [-24.0, dock + 4.5, south - 4.0], "why": "the office roof"})

    # The yard: shipping containers, two high in places (declared tops), pallets of planks, a
    # buggy to drive in up the ramp and off the dock.
    cont = ["#a55b3b", "#3f9a96", "#5f9e4f", "#c2a23a"]
    for k, (cx_, cz_, stack) in enumerate(((-50.0, 30.0, 2), (-50.0, 45.0, 1), (-30.0, 50.0, 2), (40.0, 45.0, 1), (55.0, 30.0, 2))):
        for level in range(stack):
            boxes.append(box((cx_, 1.3 + level * 2.6, cz_), (12.0, 2.6, 2.4), cont[(k + level) % 4]))
        declared.append({"min": [cx_ - 6.0, 2.5, cz_ - 1.2], "max": [cx_ + 6.0, 2.6 * stack + 1.0, cz_ + 1.2], "why": "a container's top"})
    for k in range(4):
        props.append(prop("plank", 10.0, k * 0.15, 30.0, yaw=90.0, loose=True))
        props.append(prop("plank", 10.7, k * 0.15, 30.0, yaw=90.0, loose=True))
    props.append(prop("buggy", 20.0, 0.0, 22.0, loose=True))
    props.append(prop("buggy", 0.0, 0.0, 40.0, loose=True))
    return doc("pgc_warehouse", "Warehouse",
               "A warehouse at dock height with racking full of crates, a catwalk with barrels, an office, and a yard of containers to drive round.",
               (0, 1, 60), 0.0, boxes, declared, props=props, wires=wires)


def main():
    check = "--check" in sys.argv
    MAPS.mkdir(exist_ok=True)
    bad = 0
    for d in (plots(), quarry(), slopes(), town(), islands(), site(), warehouse()):
        path = MAPS / f"{d['id']}.json"
        text = json.dumps(d, indent=1) + "\n"
        if check:
            if not path.exists() or path.read_text() != text:
                print(f"stale: {path.name}")
                bad += 1
        else:
            path.write_text(text)
            print(f"wrote {path.name}: {len(d['boxes'])} boxes")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
