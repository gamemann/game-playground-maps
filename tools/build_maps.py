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


def box(at, size, colour="floor", turn=None, material=None):
    """A box. With a material and no colour of its own (None or "floor"), it is drawn in the
    material's look (game-playground's PlaygroundMaterials); a liquid material builds a volume,
    not a body."""
    b = {"at": [r(c) for c in at], "size": [r(c) for c in size]}
    if colour is None and material is None:
        colour = "floor"
    if material is None or colour not in (None, "floor"):
        b["colour"] = colour
    if turn is not None:
        b["turn"] = [r(c) for c in turn]
    if material is not None:
        b["material"] = material
    return b


def mat(material, at, size, turn=None):
    """A box made of [material], in its own look."""
    return box(at, size, turn=turn, material=material)


def ramp_z(x, z_low, y_low, z_high, y_high, width, colour="ramp", thickness=0.5, material=None):
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
    return box(centre, (width, thickness, length), colour, (1, 0, 0, math.degrees(theta)), material)


def ramp_x(z, x_low, y_low, x_high, y_high, length, colour="ramp", thickness=0.5, material=None):
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
    return box(centre, (span, thickness, length), colour, (0, 0, 1, math.degrees(theta)), material)


def walls(size, height, top_y=0.0, colour="platform", material=None):
    half = size / 2.0
    out = []
    for side in (-1, 1):
        out.append(box((side * (half - 0.5), top_y + height / 2.0, 0), (1, height, size), colour, material=material))
        out.append(box((0, top_y + height / 2.0, side * (half - 0.5)), (size, height, 1), colour, material=material))
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


def bridge(p0, p1, width, colour="ramp", thickness=0.5, material=None):
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
    return box(centre, (width, thickness, length), colour, _turn_of(q), material)


def wall_run(axis, fixed, a0, a1, h, thick, colour, openings=(), material=None, y0=0.0):
    """A wall along [axis] ("x" or "z") at [fixed] on the other axis, from a0 to a1, h tall from
    y0, with openings cut in it: (centre, width, [(bottom, top, fill), ...]) per column, heights
    from the wall's foot. A fill of None is a doorway; a material (glass) fills the opening with a
    pane the wall's whole thickness, so nothing is recessed and a broken pane leaves a clean hole.
    Between and round the openings the wall is in pieces: full height, under, between and over."""
    out = []

    def put(b0, b1, lo, hi, col=colour, mat_=material):
        if b1 - b0 <= 1e-6 or hi - lo <= 1e-6:
            return
        mid, y = (b0 + b1) / 2.0, y0 + (lo + hi) / 2.0
        if axis == "x":
            out.append(box((mid, y, fixed), (b1 - b0, hi - lo, thick), col, material=mat_))
        else:
            out.append(box((fixed, y, mid), (thick, hi - lo, b1 - b0), col, material=mat_))

    cursor = a0
    for c, w, spans in sorted(openings, key=lambda o: o[0]):
        put(cursor, c - w / 2.0, 0.0, h)
        y = 0.0
        for lo, hi, fill in sorted(spans):
            put(c - w / 2.0, c + w / 2.0, y, lo)
            if fill:
                put(c - w / 2.0, c + w / 2.0, lo, hi, None, fill)
            y = hi
        put(c - w / 2.0, c + w / 2.0, y, h)
        cursor = c + w / 2.0
    put(cursor, a1, 0.0, h)
    return out


def window_offsets(span, keep=0.0, pitch=3.4, win_w=1.6, margin=1.2):
    """Where windows go along a wall [span] long, measured from its middle: clear of each end by
    [margin] and, with [keep], of a doorway's keep-out (-keep, keep), which is where its buttons are."""
    half = span / 2.0
    segments = [(-half + margin, -keep), (keep, half - margin)] if keep > 0.0 else [(-half + margin, half - margin)]
    offsets = []
    for s0, s1 in segments:
        length = s1 - s0
        if length < win_w:
            continue
        n = int((length - win_w) // pitch) + 1
        start = s0 + (length - ((n - 1) * pitch + win_w)) / 2.0 + win_w / 2.0
        offsets += [start + k * pitch for k in range(n)]
    return offsets


def building(cx, cz, w, d, h, door_side, colour, wall=0.4, door_w=2.4, door_h=2.8, roof=True,
             material=None, windows=(), rows=((1.0, 2.4),), win_w=1.6, roof_material=None):
    """Four walls with a doorway in one ("s" -Z, "n" +Z, "w" -X, "e" +X), a lintel over it and
    a flat roof at h. [windows] names the sides that get glass panes, a row per [rows] entry
    (sill, top), kept 3 m either side of the doorway so its buttons stay on wall.
    Returns (boxes, door_centre (x, z), door_yaw, inward (dx, dz))."""
    out = []
    hw, hd = w / 2.0, d / 2.0
    sides = {
        "s": ((cx, cz - hd + wall / 2), "x", w, (0, 1)),
        "n": ((cx, cz + hd - wall / 2), "x", w, (0, -1)),
        "w": ((cx - hw + wall / 2, cz), "z", d, (1, 0)),
        "e": ((cx + hw - wall / 2, cz), "z", d, (-1, 0)),
    }
    door = None
    for name, (centre, along, span, inward) in sides.items():
        mid, fixed = (centre[0], centre[1]) if along == "x" else (centre[1], centre[0])
        openings = []
        if name in windows:
            panes = [(lo, hi, "glass") for lo, hi in rows]
            for off in window_offsets(span, 3.0 if name == door_side else 0.0, win_w=win_w):
                openings.append((mid + off, win_w, panes))
        if name == door_side:
            openings.append((mid, door_w, [(0.0, door_h, None)]))
            door = (centre, 0.0 if along == "x" else 90.0, inward)
        out += wall_run(along, fixed, mid - span / 2.0, mid + span / 2.0, h, wall, colour, openings, material)
    if roof:
        out.append(box((cx, h + 0.15, cz), (w, 0.3, d), "platform", material=roof_material))
    return out, door[0], door[1], door[2]


def slab_with_holes(x0, x1, z0, z1, top, thick, holes, colour=None, material=None):
    """Ground from (x0, z0) to (x1, z1), [thick] deep under [top], with rectangular holes
    (hx0, hx1, hz0, hz1) cut through it: a pond or a pit is a hole with a bed and a liquid in it.
    Cut into a grid on every hole edge, and each row's solid cells merged into one box."""
    xs = sorted({x0, x1} | {c for h in holes for c in (h[0], h[1])})
    zs = sorted({z0, z1} | {c for h in holes for c in (h[2], h[3])})

    def in_hole(x, z):
        return any(h[0] < x < h[1] and h[2] < z < h[3] for h in holes)

    out = []
    for i in range(len(zs) - 1):
        za, zb = zs[i], zs[i + 1]
        run = None
        for j in range(len(xs) - 1):
            solid = not in_hole((xs[j] + xs[j + 1]) / 2.0, (za + zb) / 2.0)
            if solid and run is None:
                run = xs[j]
            if not solid and run is not None:
                out.append(box(((run + xs[j]) / 2.0, top - thick / 2.0, (za + zb) / 2.0), (xs[j] - run, thick, zb - za), colour, material=material))
                run = None
        if run is not None:
            out.append(box(((run + xs[-1]) / 2.0, top - thick / 2.0, (za + zb) / 2.0), (xs[-1] - run, thick, zb - za), colour, material=material))
    return out


def pit_steps(axis, edge, into, lo, hi, y_top, y_bed, material="rock", colour=None, tread=1.0, max_rise=0.4):
    """Steps up out of a pit to its edge at [edge] on [axis] ("x" or "z"), running [into] the pit
    (+1 or -1) and spanning lo..hi on the other axis, wall to wall, so their sides face nothing.
    Each rises at most 0.4 m, a walk; the last one down is the bed itself."""
    n = max(1, math.ceil((y_top - y_bed) / max_rise - 1e-9))
    rise = (y_top - y_bed) / n
    out = []
    for k in range(1, n):
        t = y_top - k * rise
        a, b = edge + into * (k - 1) * tread, edge + into * k * tread
        mid, length = (a + b) / 2.0, abs(b - a)
        if axis == "x":
            out.append(box((mid, (t + y_bed) / 2.0, (lo + hi) / 2.0), (length, t - y_bed, hi - lo), colour, material=material))
        else:
            out.append(box(((lo + hi) / 2.0, (t + y_bed) / 2.0, mid), (hi - lo, t - y_bed, length), colour, material=material))
    return out


def trampoline(x, z, floor_y=0.0, size=3.0):
    """A rubber pad 0.3 m thick (a step): game-playground jumps a player 1.8 times as high off it."""
    return mat("rubber", (x, floor_y + 0.15, z), (size, 0.3, size))


def bush(x, z, floor_y=0.0, size=3.0, height=2.0):
    """Foliage: drawn, walked through and hidden in, with no collider."""
    return mat("foliage", (x, floor_y + height / 2.0, z), (size, height, size))


# --- Build Plots ---------------------------------------------------------------------------

PLOT_COLOURS = ["#3b6ea5", "#a55b3b", "#5f9e4f", "#8d5fa8", "#c2a23a", "#3f9a96", "#b04f72", "#6d7480"]
# Each plot is a different ground to build on (2026-10-07): an ice plot slides what is put on it,
# a rubber one throws its builder 1.8 times as high, sand and snow slow them down.
PLOT_MATERIALS = ["concrete", "wood", "sand", "snow", "ice", "metal", "dirt", "rubber"]


def plots():
    size, wall_h = 160.0, 6.0
    # A pond in the south-east corner is a hole in the grass, 2.5 m deep: the ground is 3.5 m
    # thick so the hole has sides, and steps across its whole west edge are the way out.
    pond = (57.0, 75.0, 57.0, 75.0)
    boxes = slab_with_holes(-size / 2, size / 2, -size / 2, size / 2, 0.0, 3.5, [pond], material="grass")
    boxes += walls(size, wall_h, material="concrete")
    # The spawn plaza in the middle, and eight plots round it on a 40 m pitch: 26 m of pad
    # each, 14 m of path between. A pad is 0.2 m: a step, not a climb.
    boxes.append(box((0, 0.1, 0), (20, 0.2, 20), "start", material="concrete"))
    n = 0
    for gx in (-1, 0, 1):
        for gz in (-1, 0, 1):
            if gx == 0 and gz == 0:
                continue
            cx, cz = gx * 40.0, gz * 40.0
            boxes.append(mat(PLOT_MATERIALS[n], (cx, 0.1, cz), (26, 0.2, 26)))
            # The claim pad: on the path, on the plot's side nearest the plaza.
            dx, dz = -gx, -gz
            if dx != 0 and dz != 0:
                dz = 0
            boxes.append(box((cx + dx * 14.5, 0.05, cz + dz * 14.5), (2, 0.1, 2), "boost", material="metal"))
            n += 1
    # A viewing deck in the north-west corner, 4 m up, and a 20-degree ramp onto it.
    boxes.append(mat("wood", (-66, 3.75, -66), (10, 0.5, 10)))
    boxes.append(ramp_z(-66, -50.0, 0.0, -61.0, 4.0, 6, None, material="wood"))
    # Two trampolines on the plaza, and the pond: water 2.2 m deep over a sand bed, its surface
    # 0.3 m under the grass, with bushes beside it.
    for tz in (-6.0, 6.0):
        boxes.append(trampoline(-6.0, tz, 0.2))
    px0, px1, pz0, pz1 = pond
    boxes.append(mat("sand", ((px0 + px1) / 2, -3.0, (pz0 + pz1) / 2), (px1 - px0, 1.0, pz1 - pz0)))
    boxes += pit_steps("x", px0, 1, pz0, pz1, 0.0, -2.5, "rock")
    boxes.append(mat("water", ((px0 + px1) / 2, (-2.5 - 0.3) / 2, (pz0 + pz1) / 2), (px1 - px0, 2.2, pz1 - pz0)))
    for at in ((56.0, 77.0), (66.0, 77.5), (77.5, 62.0), (54.5, 55.0)):
        boxes.append(bush(at[0], at[1]))
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
    # The pit floor is dirt, 4 m thick, with a flooded sump cut into its south-east corner: a hole
    # 3 m deep against two terrace walls, water to 0.3 m under the floor, and steps across its
    # whole west edge as the way out (a swimmer also climbs the 0.3 m edge anywhere).
    sump = (6.0, 30.0, -30.0, -6.0)
    boxes += slab_with_holes(-70.0, 70.0, -70.0, 70.0, floor_y, 4.0, [sump], "#5a4e42", "dirt")
    # The rim (top y 0), a frame from 50 to 70 out.
    rim = "#8a7a62"
    boxes.append(box((0, -6, 60), (140, 12, 20), rim, material="rock"))
    boxes.append(box((0, -6, -60), (140, 12, 20), rim, material="rock"))
    boxes.append(box((60, -6, 0), (20, 12, 100), rim, material="rock"))
    boxes.append(box((-60, -6, 0), (20, 12, 100), rim, material="rock"))
    # The terrace (top y -6), a frame from 30 to 50 out.
    terrace = "#73654f"
    boxes.append(box((0, -9, 40), (100, 6, 20), terrace, material="rock"))
    boxes.append(box((0, -9, -40), (100, 6, 20), terrace, material="rock"))
    boxes.append(box((40, -9, 0), (20, 6, 60), terrace, material="rock"))
    boxes.append(box((-40, -9, 0), (20, 6, 60), terrace, material="rock"))
    # A 3 m wall round the rim's outer edge, so a thrown prop stays in the quarry.
    boxes += walls(140, 3.0, 0.0, "#5e5547", "rock")
    declared += wall_tops(140, 3.0, "the tops of the rim's walls, 3 m up")
    # Ramps down, one per level per side, offset so the way down is a walk round. Dirt, which
    # is a walk (rock and dirt hold a foot; ice here would be a slide nobody climbs).
    boxes.append(ramp_z(-20, 30.0, b_y, 50.0, 0.0, 6, None, material="dirt"))
    boxes.append(ramp_z(20, 10.0, floor_y, 30.0, b_y, 6, None, material="dirt"))
    boxes.append(ramp_z(20, -30.0, b_y, -50.0, 0.0, 6, None, material="dirt"))
    boxes.append(ramp_z(-20, -10.0, floor_y, -30.0, b_y, 6, None, material="dirt"))
    # Rails: a line across the pit floor and one along the north terrace. 0.15 m: a step.
    rail = "#9aa0a6"
    for z in (-0.7, 0.7):
        boxes.append(box((0, floor_y + 0.075, z), (56, 0.15, 0.2), rail, material="metal"))
    for z in (39.3, 40.7):
        boxes.append(box((8, b_y + 0.075, z), (80, 0.15, 0.2), rail, material="metal"))
    # A cart on the pit rails, 1.0 m above the floor: a climb, just.
    boxes.append(box((-8, floor_y + 0.15 + 0.425, 0), (2.0, 0.85, 1.2), "#7a4a2a", material="metal"))
    # Ore piles, climbable, and two boulders nobody climbs. The one in the sump stands on its bed
    # and breaks the surface: the same 2.5 m over the floor as the other.
    for at in ((0, -16), (-14, 14), (18, 12)):
        boxes.append(box((at[0], floor_y + 0.45, at[1]), (2.4, 0.9, 2.4), "#6b6f4e", material="rock"))
    sump_bed = floor_y - 3.0
    for at in ((-18, -18), (22, -20)):
        foot = sump_bed if sump[0] < at[0] < sump[1] and sump[2] < at[1] < sump[3] else floor_y
        tall = floor_y + 2.5 - foot
        boxes.append(box((at[0], foot + tall / 2.0, at[1]), (3, tall, 3), "#5c5c5c", material="rock"))
        declared.append({"min": [at[0] - 1.5, floor_y + 2.5, at[1] - 1.5],
                         "max": [at[0] + 1.5, floor_y + 3.0, at[1] + 1.5],
                         "why": "a boulder's top, 2.5 m up: a climb nobody makes"})
    sx0, sx1, sz0, sz1 = sump
    boxes.append(mat("mud", ((sx0 + sx1) / 2, sump_bed - 0.5, (sz0 + sz1) / 2), (sx1 - sx0, 1.0, sz1 - sz0)))
    boxes += pit_steps("x", sx0, 1, sz0, sz1, floor_y, sump_bed, "rock")
    boxes.append(mat("water", ((sx0 + sx1) / 2, (sump_bed + floor_y - 0.3) / 2, (sz0 + sz1) / 2), (sx1 - sx0, 2.7, sz1 - sz0)))
    # A mud patch on the pit floor by the north ramp's foot: a slog, 0.1 m (a step).
    boxes.append(mat("mud", (8, floor_y + 0.05, 20), (12, 0.1, 10)))
    props, wires = [], []
    # A blasting hut on the west terrace: a lever outside opens its door, and inside are the
    # barrels (with pg_destruction on, a shot one goes up and takes its neighbours with it).
    hut, door_at, door_yaw, inward = building(-40.0, 0.0, 10.0, 8.0, 4.0, "e", "#7b5a3a", material="wood", roof_material="wood")
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
    for cx_, cz_ in ((-5, -21), (-22, 6)):
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
    # A frozen pond on the west side is a hole in the grass under a sheet of thin ice.
    pond = (-60.0, -40.0, 20.0, 36.0)
    boxes = slab_with_holes(-size / 2, size / 2, -size / 2, size / 2, 0.0, 3.5, [pond], material="grass")
    boxes += walls(size, wall_h, material="concrete")
    boxes.append(box((0, 0.1, 80), (12, 0.2, 12), "start", material="concrete"))
    # The hill: a long 14-degree walk up from the spawn side to a deck 20 m up, and a
    # 24-degree slope down the far side. Measured (2026-10-07): at the catalogue's friction
    # (1.0) a plank or crate set on the slope settles and stays, so it can be built on; with
    # its friction at 0.2 (the tool gun's Edit properties or Physical properties) it slides
    # about 35 m to the bottom, and prop surfing carries whoever stands on it. The hill is grass
    # and the far slope snow: both hold a crate (0.8 and 0.5 against the 0.25 and 0.45 the two
    # slopes need) and a walker.
    top = 20.0
    # A lighter green than the ground: in grass's own look the hill vanished into the plate in
    # the render, and a hill nobody can see is not the map's landmark.
    boxes.append(ramp_z(0, 70.0, 0.0, -10.0, top, 30, "#7fae55", material="grass"))
    boxes.append(box((0, top - 0.25, -20), (30, 0.5, 20), "platform", material="wood"))
    boxes.append(ramp_z(0, -75.0, 0.0, -30.0, top, 30, None, material="snow"))
    # At the far slope's foot, an ice run-out to the wall: whatever comes down the snow keeps
    # going. Flush with the slope's foot, 0.1 m (a step).
    boxes.append(mat("ice", (0, 0.05, -82.0), (30, 0.1, 14.0)))
    # The pen on the deck: a 1 m wall round an 8 m square, the "stand in the box" spot to be
    # picked up and thrown from. 1.0 m is under the 1.035 m a jump climbs, so nobody is shut in.
    pen = "boost"
    for side in (-1, 1):
        boxes.append(box((side * 4.15, top + 0.5, -20), (0.3, 1.0, 8.6), pen, material="wood"))
        boxes.append(box((0, top + 0.5, -20 + side * 4.15), (8.0, 1.0, 0.3), pen, material="wood"))
    # A halfpipe along Z on the east side: two 31-degree faces 14 m apart, each topped by a
    # 5 m ledge, for riding a prop back and forth or dropping in on one. Wood faces.
    lip = 6.0
    boxes.append(ramp_x(0, 48.0, 0.0, 38.0, lip, 60, None, material="wood"))
    boxes.append(ramp_x(0, 62.0, 0.0, 72.0, lip, 60, None, material="wood"))
    boxes.append(box((35.5, lip / 2.0, 0), (5, lip, 60), "platform", material="concrete"))
    boxes.append(box((74.5, lip / 2.0, 0), (5, lip, 60), "platform", material="concrete"))
    declared = wall_tops(size, wall_h, "the tops of the walls, 6 m up: they keep props in")
    # The frozen pond: water 2.4 m deep under thin ice level with the grass, which holds a walker
    # and breaks under a landing or a shot (game-playground's thin ice). Steps across its east
    # edge climb out; under the ice they and the bed are out of reach, and declared.
    fx0, fx1, fz0, fz1 = pond
    boxes.append(mat("sand", ((fx0 + fx1) / 2, -3.0, (fz0 + fz1) / 2), (fx1 - fx0, 1.0, fz1 - fz0)))
    boxes += pit_steps("x", fx1, -1, fz0, fz1, 0.0, -2.5, "rock")
    boxes.append(mat("water", ((fx0 + fx1) / 2, (-2.5 - 0.1) / 2, (fz0 + fz1) / 2), (fx1 - fx0, 2.4, fz1 - fz0)))
    boxes.append(mat("thin_ice", ((fx0 + fx1) / 2, -0.05, (fz0 + fz1) / 2), (fx1 - fx0, 0.1, fz1 - fz0)))
    declared.append({"min": [fx0, -2.5, fz0], "max": [fx1, -0.1, fz1], "why": "the pond's bed and steps, under the ice until somebody breaks it"})
    # A snow bank round it, 2 m wide and 0.1 m (a step): drawn without one, the ice was a pale
    # square on the lawn and nothing said "pond".
    for side in (-1, 1):
        boxes.append(mat("snow", ((fx0 + fx1) / 2, 0.05, (fz1 + 1.0) if side > 0 else (fz0 - 1.0)), (fx1 - fx0 + 4.0, 0.1, 2.0)))
        boxes.append(mat("snow", ((fx1 + 1.0) if side > 0 else (fx0 - 1.0), 0.05, (fz0 + fz1) / 2), (2.0, 0.1, fz1 - fz0)))
    # Two trampolines by the spawn.
    for at in ((-30.0, 60.0), (-24.0, 66.0)):
        boxes.append(trampoline(at[0], at[1]))
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
    boxes = [mat("grass", (0, -0.5, 0), (size, 1, size))]
    boxes += walls(size, wall_h, colour="#6d7480", material="concrete")
    declared = wall_tops(size, wall_h, "the town's outer walls, 8 m up")
    props, wires = [], []

    # Two roads crossing in the middle, 14 m wide, with a 0.15 m pavement (a step) either side.
    for along in ("x", "z"):
        if along == "x":
            boxes.append(box((0, 0.01, 0), (size - 2, 0.02, 14), ROAD, material="concrete"))
        else:
            # A hair higher than the other road, so the crossing is one surface and not two
            # fighting for the same depth.
            boxes.append(box((0, 0.0125, 0), (14, 0.025, size - 2), ROAD, material="concrete"))
    # The plaza on the north-east block: a fountain (a 0.5 m ring, a 2.5 m column), benches.
    px, pz = 45.0, 45.0
    boxes.append(box((px, 0.075, pz), (70, 0.15, 70), KERB, material="concrete"))
    for side in (-1, 1):
        boxes.append(box((px + side * 4.75, 0.4, pz), (0.5, 0.5, 10), "#9aa3ad", material="rock"))
        boxes.append(box((px, 0.4, pz + side * 4.75), (9, 0.5, 0.5), "#9aa3ad", material="rock"))
    boxes.append(box((px, 1.4, pz), (1.2, 2.5, 1.2), "#9aa3ad", material="rock"))
    # The fountain holds water now: 0.4 m inside the ring, a paddle (a player swims from 1 m).
    boxes.append(mat("water", (px, 0.35, pz), (9.0, 0.4, 9.0)))
    declared.append({"min": [px - 0.6, 2.5, pz - 0.6], "max": [px + 0.6, 3.0, pz + 0.6],
                     "why": "the top of the fountain's column, 2.5 m up"})
    for at in ((px - 14, pz - 14), (px + 14, pz - 14), (px - 14, pz + 14), (px + 14, pz + 14)):
        boxes.append(box((at[0], 0.4, at[1]), (3, 0.5, 0.8), "#7b5a3a", material="wood"))
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
    boxes.append(box((sx_, 0.15 + 0.45, sz_), (16, 0.9, 6), "#7b5a3a", material="wood"))
    for side in (-1, 1):
        boxes.append(box((sx_ + side * 9.0, 0.15 + 0.225, sz_), (2, 0.45, 4), "#7b5a3a", material="wood"))
    # Market stalls along the west of the plaza: a counter and its goods, loose.
    for i in range(3):
        mz = pz - 14 + i * 12
        boxes.append(box((px - 24, 0.15 + 0.5, mz), (2, 1.0, 5), "#a55b3b", material="wood"))
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
        boxes.append(box((cx, 0.075, cz), (w + 8, 0.15, d + 8), KERB, material="concrete"))
        # Glass in every wall but the one the roof ramp climbs: shop windows either side of the
        # door, a row at 1.0-2.4 m round the rest, and a second at 4.0-5.4 m on the tall ones.
        ramp_side = "e" if cx > 0 else "w"
        rows = ((1.0, 2.4), (4.0, 5.4)) if h >= 7.0 else ((1.0, 2.4),)
        built, door_at, door_yaw, inward = building(cx, cz, w, d, h, door_side, colour, material="concrete",
                                                    windows=[k for k in "nsew" if k != ramp_side], rows=rows,
                                                    roof_material="concrete")
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
        boxes.append(ramp_z(rx, top_z + sz * run, 0.0, top_z, roof_top, 3.6, material="concrete"))
        boxes.append(box((rx, roof_top / 2.0, top_z - sz * 1.5), (3.6, roof_top, 3.0), colour, material="concrete"))
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
    boxes.append(box((50, 0.03, -80), (40, 0.06, 16), "#2e3136", material="concrete"))
    # Hedges on the plaza to hide in, and a trampoline by the fountain.
    for at in ((70.0, 40.0), (70.0, 50.0), (58.0, 27.0), (32.0, 63.0), (24.0, 66.0)):
        boxes.append(bush(at[0], at[1], 0.15, 2.5, 1.6))
    boxes.append(trampoline(px + 16.0, pz, 0.15, 4.0))
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
    boxes = [mat("grass", (0, -0.5, 0), (size, 1, size))]
    boxes += walls(size, wall_h, colour="#6d7480", material="concrete")
    declared = wall_tops(size, wall_h, "the outer walls, 6 m up")
    props = []

    ring, half, thick = 55.0, 10.0, 3.0
    centres, tops = [], []
    for i in range(6):
        a = math.radians(i * 60.0)
        centres.append((ring * math.cos(a), ring * math.sin(a)))
        tops.append(8.0 + i * 5.0)
    for i, (c, top) in enumerate(zip(centres, tops)):
        boxes.append(box((c[0], top - thick / 2.0, c[1]), (2 * half, thick, 2 * half), ISLAND_COLOURS[i], material="grass"))

    def link(i, j, width, colour, material=None):
        ci, cj = centres[i], centres[j]
        dx, dz = cj[0] - ci[0], cj[1] - ci[1]
        n = math.hypot(dx, dz)
        d = (dx / n, dz / n)
        a = _edge(ci, d, half)
        b = _edge(cj, (-d[0], -d[1]), half)
        return bridge((a[0], tops[i], a[1]), (b[0], tops[j], b[1]), width, colour, material=material)

    # Bridges up the ring, 5 m a step: a gentle walk, 4 m wide and no rails, in wood.
    for i in range(5):
        boxes.append(link(i, i + 1, 4.0, None, "wood"))
    # And the slide: from the top island straight back down to the first, 25 m in 32, about
    # 38 degrees. Ice since 2026-10-07, so it is a slide for a player as well as a prop: it was
    # walkable, just, and the bridges are the way up.
    boxes.append(link(5, 0, 6.0, None, "ice"))
    # From the ground up to the first island.
    c0 = centres[0]
    boxes.append(ramp_z(c0[0], c0[1] - half - 36.0, 0.0, c0[1] - half, tops[0], 5.0, None, material="wood"))
    # The floor in the middle of the ring is lava, in a 0.8 m rock rim (a jump): a fall off an
    # island's inner corner or a bridge's inside edge lands in it and goes back to the spawn, and
    # a prop thrown in melts. Everything outside the rim is grass, which leads back to the ramp.
    lava = 38.0
    for side in (-1, 1):
        boxes.append(mat("rock", (side * (lava + 0.5), 0.4, 0), (1.0, 0.8, 2 * lava + 2.0)))
        boxes.append(mat("rock", (0, 0.4, side * (lava + 0.5)), (2 * lava, 0.8, 1.0)))
    boxes.append(mat("lava", (0, 0.25, 0), (2 * lava, 0.5, 2 * lava)))

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
    # Beach balls on the grass outside the ring (they were in its middle, which is lava now).
    for at in ((-95, 50), (95, -45), (-50, -95), (45, 95)):
        props.append(prop("beach_ball", at[0], 0.0, at[1], loose=True))
    # Bushes on four of the islands.
    for i in (0, 1, 2, 4):
        boxes.append(bush(centres[i][0] + 5.0, centres[i][1] - 5.0, tops[i]))
    return doc("pgc_islands", "Sky Islands",
               "Six islands climbing a ring on bridges, a slide from the top one back to the first, and nothing between you and the ground.",
               (c0[0], 1, c0[1] - half - 40.0), 180.0, boxes, declared, props=props)


# --- Construction Site ---------------------------------------------------------------------

CONCRETE = "#8a8a84"
DIRT = "#7a6548"


def site():
    size, wall_h = 180.0, 3.0
    # A flooded excavation for the next building, in the south-east: a hole in the dirt.
    dig = (30.0, 50.0, -57.0, -43.0)
    boxes = slab_with_holes(-size / 2, size / 2, -size / 2, size / 2, 0.0, 3.5, [dig], DIRT, "dirt")
    boxes += walls(size, wall_h, colour="#c2a23a", material="metal")
    declared = wall_tops(size, wall_h, "the site fence, 3 m up")
    props, wires = [], []

    # The frame: a 30 x 20 m footprint, floors every 4.5 m, three of them open slabs on
    # 0.6 m columns, the top one open to the sky. Climbed by a switchback on the east side:
    # lane A (next to the frame) carries the first and third ramps, lane B the second, and a
    # landing at each floor spans both lanes and touches the slab's edge.
    fx, fz, fw, fd, storey = -25.0, -20.0, 30.0, 20.0, 4.5
    boxes.append(box((fx, 0.15, fz), (fw, 0.3, fd), CONCRETE, material="concrete"))
    floors = [storey * k for k in (1, 2, 3)]
    for y in floors:
        boxes.append(box((fx, y - 0.15, fz), (fw, 0.3, fd), CONCRETE, material="concrete"))
    for cx_ in (fx - fw / 2 + 0.3, fx, fx + fw / 2 - 0.3):
        for cz_ in (fz - fd / 2 + 0.3, fz + fd / 2 - 0.3):
            boxes.append(box((cx_, floors[-1] / 2.0, cz_), (0.6, floors[-1] - 0.3, 0.6), CONCRETE, material="concrete"))
    east = fx + fw / 2.0
    lane_a, lane_b, lane_w = east + 1.8, east + 5.4, 3.6
    z0 = fz - fd / 2.0  # flush with the frame: 1 m in left a 0.4 m slot against the corner column
    run = storey * 1.8
    # Ramp 1 (lane A, rising +Z) to floor 1; landing 1; ramp 2 (lane B, rising -Z) to floor 2;
    # landing 2; ramp 3 (lane A, rising +Z, 9 m over ramp 1) to floor 3; landing 3.
    boxes.append(ramp_z(lane_a, z0, 0.0, z0 + run, floors[0], lane_w, material="wood"))
    boxes.append(box((east + 3.6, floors[0] - 0.15, z0 + run + 1.5), (7.2, 0.3, 3.0), CONCRETE, material="concrete"))
    boxes.append(ramp_z(lane_b, z0 + run, floors[0], z0, floors[1], lane_w, material="wood"))
    boxes.append(box((east + 3.6, floors[1] - 0.15, z0 - 1.5), (7.2, 0.3, 3.0), CONCRETE, material="concrete"))
    boxes.append(ramp_z(lane_a, z0, floors[1], z0 + run, floors[2], lane_w, material="wood"))
    boxes.append(box((east + 3.6, floors[2] - 0.15, z0 + run + 1.5), (7.2, 0.3, 3.0), CONCRETE, material="concrete"))

    # The tower crane: a 2 m mast 28 m tall, and a jib along X over the frame.
    crane_x, crane_z, mast = 15.0, -38.0, 28.0
    boxes.append(box((crane_x, mast / 2.0, crane_z), (2, mast, 2), "#d4a017", material="metal"))
    boxes.append(box((crane_x - 12.0, mast + 0.5, crane_z), (40, 1.0, 1.2), "#d4a017", material="metal"))
    boxes.append(box((crane_x + 6.0, mast - 1.0, crane_z), (4, 2.0, 2.5), "#5a5d63", material="metal"))
    declared.append({"min": [crane_x - 32.0, mast - 0.2, crane_z - 1.3], "max": [crane_x + 8.0, mast + 1.5, crane_z + 1.3],
                     "why": "the crane's jib and mast top, 28 m up"})

    # A dirt kicker for the buggies: up 2.5 m at 15 degrees, a 6 m table, and down again.
    kx, kz, mound = 40.0, 35.0, "#5e4a33"
    boxes.append(ramp_z(kx, kz - 18.0, 0.0, kz - 9.0, 2.5, 8.0, mound, material="dirt"))
    boxes.append(box((kx, 1.25, kz - 6.0), (8.0, 2.5, 6.0), mound, material="dirt"))
    boxes.append(ramp_z(kx, kz + 6.0, 0.0, kz - 3.0, 2.5, 8.0, mound, material="dirt"))
    # A bumps track beside it: three mounds 1.2 m high, up and down at about 13 degrees.
    for k in range(3):
        bz = -10.0 + k * 14.0
        boxes.append(ramp_z(62.0, bz - 5.0, 0.0, bz, 1.2, 6.0, mound, material="dirt"))
        boxes.append(ramp_z(62.0, bz + 5.0, 0.0, bz, 1.2, 6.0, mound, material="dirt"))
    props.append(prop("buggy", kx - 10.0, 0.0, kz - 30.0, loose=True))
    props.append(prop("buggy", kx + 10.0, 0.0, kz - 30.0, loose=True))

    # The site office, a door on a button either side.
    office, door_at, door_yaw, inward = building(-50.0, 45.0, 12.0, 8.0, 3.5, "s", "#e8e2d0", material="wood",
                                                 windows=("n", "e", "w"), roof_material="metal")
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

    # The excavation: muddy water 2.1 m deep over a mud bed, its surface 0.4 m under the dirt,
    # steps up its north edge, and a band of mud trodden round that edge.
    dx0, dx1, dz0, dz1 = dig
    boxes.append(mat("mud", ((dx0 + dx1) / 2, -3.0, (dz0 + dz1) / 2), (dx1 - dx0, 1.0, dz1 - dz0)))
    boxes += pit_steps("z", dz1, -1, dx0, dx1, 0.0, -2.5, "dirt")
    boxes.append(box(((dx0 + dx1) / 2, (-2.5 - 0.4) / 2, (dz0 + dz1) / 2), (dx1 - dx0, 2.1, dz1 - dz0), "#5a6650", material="water"))
    boxes.append(mat("mud", ((dx0 + dx1) / 2, 0.05, dz1 + 5.0), (dx1 - dx0, 0.1, 10.0)))
    # A sand heap (1.5 m, up and down at about 20 degrees) and a glazing rack: four panes of real
    # glass standing on a pallet, 1.5 m apart, to be shot out or driven through.
    hx, hz = -10.0, 36.0
    boxes.append(ramp_z(hx, hz - 6.0, 0.0, hz - 2.0, 1.5, 6.0, None, material="sand"))
    boxes.append(mat("sand", (hx, 0.75, hz), (6.0, 1.5, 4.0)))
    boxes.append(ramp_z(hx, hz + 6.0, 0.0, hz + 2.0, 1.5, 6.0, None, material="sand"))
    gx = -25.0
    boxes.append(mat("wood", (gx, 0.075, 40.0), (6.0, 0.15, 2.2)))
    for k in range(4):
        boxes.append(mat("glass", (gx - 2.25 + k * 1.5, 0.15 + 1.2, 40.0), (0.1, 2.4, 1.8)))

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
    boxes = [box((0, -0.5, 0), (size, 1, size), "#5a5d63", material="concrete")]
    boxes += walls(size, wall_h, colour="#6d7480", material="metal")
    declared = wall_tops(size, wall_h, "the yard fence, 4 m up")
    props, wires = [], []

    # The hall: 80 x 50 m, its floor at dock height (1.2 m, a climb a jump does not make), walls
    # 12 m and a roof. South wall: two 8 m loading doorways 6 m high; the east one has a ramp
    # up from the yard, the west one is a sheer dock edge to drive off.
    hx, hz, hw, hd, hh, dock = 0.0, -20.0, 80.0, 50.0, 12.0, 1.2
    wall_c, wt = "#9c7134", 0.6
    boxes.append(box((hx, dock / 2.0, hz), (hw, dock, hd), "#7d8189", material="concrete"))
    south = hz + hd / 2.0
    top = dock + hh
    # The north, east and west walls carry a row of high windows, 3 m panes from 8 to 10.5 m over
    # the floor: 1.6 m over the catwalk (6 m), so nobody climbs into one, and a shot breaks one.
    high = [(8.0, 10.5, "glass")]
    for side in (-1, 1):
        x = hx + side * (hw / 2 - wt / 2)
        openings = [(hz + off, 3.0, high) for off in window_offsets(hd, pitch=7.0, win_w=3.0, margin=3.5)]
        boxes += wall_run("z", x, hz - hd / 2, hz + hd / 2, hh, wt, wall_c, openings, "metal", dock)
    openings = [(hx + off, 3.0, high) for off in window_offsets(hw, pitch=7.0, win_w=3.0, margin=3.5)]
    boxes += wall_run("x", hz - hd / 2 + wt / 2, hx - hw / 2, hx + hw / 2, hh, wt, wall_c, openings, "metal", dock)
    # South wall in five pieces round the two doorways (centred at x -20 and +20, 8 m wide).
    door_xs, door_w, door_h = (-20.0, 20.0), 8.0, 6.0
    edges = [-hw / 2, door_xs[0] - door_w / 2, door_xs[0] + door_w / 2, door_xs[1] - door_w / 2, door_xs[1] + door_w / 2, hw / 2]
    for k in (0, 2, 4):
        a, b = edges[k], edges[k + 1]
        boxes.append(box(((a + b) / 2, dock + hh / 2, south - wt / 2), (b - a, hh, wt), wall_c, material="metal"))
    for dx in door_xs:
        boxes.append(box((dx, dock + door_h + (hh - door_h) / 2, south - wt / 2), (door_w, hh - door_h, wt), wall_c, material="metal"))
    boxes.append(box((hx, top + 0.2, hz), (hw, 0.4, hd), "#6f7480", material="metal"))
    declared.append({"min": [-hw / 2, top, hz - hd / 2], "max": [hw / 2, top + 1.0, hz + hd / 2], "why": "the warehouse roof"})
    # The ramp up at the east doorway; the west one is the dock edge.
    boxes.append(ramp_z(door_xs[1], south + 6.0, 0.0, south, dock, door_w, material="concrete"))

    # Racking: four rows of 30 m, 2 m deep, shelves at 2.5 and 5 m above the floor on posts
    # every 5 m, aisles of 6 m. The shelves are declared: nobody walks up a rack.
    rack_c, shelf_c = "#3b6ea5", "#c2a23a"
    for row, rz in enumerate((-36.0, -28.0, -20.0, -12.0)):
        for px_ in range(7):
            x = -25.0 + px_ * 5.0
            for dz in (-0.85, 0.85):
                boxes.append(box((x, dock + 2.75, rz + dz), (0.3, 5.5, 0.3), rack_c, material="metal"))
        for level in (2.5, 5.0):
            boxes.append(box((-10.0, dock + level, rz), (30.3, 0.2, 2.0), shelf_c, material="wood"))
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
    boxes.append(box(((cw_start + cw_end) / 2, cw_y - 0.15, north + 1.25), (cw_end - cw_start, 0.3, 2.5), "#5a5d63", material="metal"))
    boxes.append(box((hx + hw / 2 - wt - 1.25, cw_y - 0.15, hz - 5.0), (2.5, 0.3, hd - 10.0 - wt), "#5a5d63", material="metal"))
    boxes.append(ramp_x(north + 1.25, -hw / 2 + wt, dock, -hw / 2 + wt + 14.0, cw_y, 2.5, material="metal"))
    for k in range(4):
        props.append(prop("barrel", 0.0 + k * 6.0, cw_y, north + 1.25, loose=True))

    # The office in the south-west corner of the hall, a door on a button.
    # Glazed on its three other sides, so whoever is in it can be seen (and shot at) from the floor.
    office, door_at, door_yaw, inward = building(-30.0, south - 8.0, 12.0, 8.0, 3.5, "e", "#e8e2d0", material="wood",
                                                 windows=("n", "s", "w"), roof_material="wood")
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
            boxes.append(box((cx_, 1.3 + level * 2.6, cz_), (12.0, 2.6, 2.4), cont[(k + level) % 4], material="metal"))
        declared.append({"min": [cx_ - 6.0, 2.5, cz_ - 1.2], "max": [cx_ + 6.0, 2.6 * stack + 1.0, cz_ + 1.2], "why": "a container's top"})
    for k in range(4):
        props.append(prop("plank", 10.0, k * 0.15, 30.0, yaw=90.0, loose=True))
        props.append(prop("plank", 10.7, k * 0.15, 30.0, yaw=90.0, loose=True))
    props.append(prop("buggy", 20.0, 0.0, 22.0, loose=True))
    props.append(prop("buggy", 0.0, 0.0, 40.0, loose=True))

    # A cold store on the hall floor east of the racking: an open doorway facing the loading
    # doors, an ice floor (0.05 m, a step) and two blocks of ice, and crates loose on it, which a
    # push sends across the room.
    cs_x, cs_z, cs_w, cs_d = 22.0, -30.0, 12.0, 10.0
    store, _cs_door, _cs_yaw, _cs_in = building(cs_x, cs_z, cs_w, cs_d, 3.5, "n", "#cfe3ea", material="metal", roof_material="metal")
    for b in store:
        b["at"][1] = r(b["at"][1] + dock)
    boxes += store
    boxes.append(mat("ice", (cs_x, dock + 0.025, cs_z), (cs_w - 0.8, 0.05, cs_d - 0.8)))
    for at in ((26.0, -33.0), (18.5, -33.0)):
        boxes.append(mat("ice", (at[0], dock + 0.05 + 0.5, at[1]), (1.0, 1.0, 1.0)))
    declared.append({"min": [cs_x - cs_w / 2, dock + 3.5, cs_z - cs_d / 2], "max": [cs_x + cs_w / 2, dock + 4.5, cs_z + cs_d / 2], "why": "the cold store's roof"})
    for k in range(3):
        props.append(prop("crate", 20.0 + k * 2.0, dock + 0.05, -29.0, loose=True, tint="#cfe3ea"))
    return doc("pgc_warehouse", "Warehouse",
               "A warehouse at dock height with racking full of crates, a catwalk with barrels, an office, and a yard of containers to drive round.",
               (0, 1, 60), 0.0, boxes, declared, props=props, wires=wires)


# --- Canyon ----------------------------------------------------------------------------------

def canyon():
    size, rim, half_gap = 220.0, 20.0, 20.0
    wall_h = rim + 4.0
    rock, mesa = "#9c6b45", "#b8875a"
    # The river is a channel 10 m wide cut down the canyon's middle, wall to wall: the floor is
    # 4 m thick so the channel has sides, and its two ends are under the outer walls.
    river = (-5.0, 5.0, -size / 2 + 1.0, size / 2 - 1.0)
    boxes = slab_with_holes(-size / 2, size / 2, -size / 2, size / 2, 0.0, 4.0, [river], "#7a6548", "dirt")
    boxes += walls(size, wall_h, colour=rock, material="rock")
    declared = wall_tops(size, wall_h, "the outer walls, 24 m up: 4 m over the mesas")
    props = []

    # Two mesas, the canyon 40 m wide between them, a river down its middle.
    mesa_w = size / 2.0 - half_gap
    for side in (-1, 1):
        boxes.append(box((side * (half_gap + mesa_w / 2.0), rim / 2.0, 0), (mesa_w, rim, size), mesa, material="rock"))
    # The river: water to 0.15 m under the floor, over a sand bed that is shallow at both ends
    # (0.55 m of water, waded, and 0.7 m up to the floor, a jump) and 2.85 m deep for 100 m in the
    # middle, under the road bridge and the broken bridge, so a buggy that misses the jump lands in
    # it. Down to the deep part and up again by steps the width of the channel, a walk.
    rx0, rx1, rz0, rz1 = river
    shallow, deep, surface = -0.7, -3.0, -0.15
    s0, s1 = -35.0, 70.0
    boxes.append(mat("sand", (0, (-4.0 + shallow) / 2, (rz0 + s0) / 2), (rx1 - rx0, shallow + 4.0, s0 - rz0)))
    boxes.append(mat("sand", (0, (-4.0 + deep) / 2, (s0 + s1) / 2), (rx1 - rx0, deep + 4.0, s1 - s0)))
    boxes.append(mat("sand", (0, (-4.0 + shallow) / 2, (s1 + rz1) / 2), (rx1 - rx0, shallow + 4.0, rz1 - s1)))
    boxes += pit_steps("z", s0, 1, rx0, rx1, shallow, deep, "rock")
    boxes += pit_steps("z", s1, -1, rx0, rx1, shallow, deep, "rock")
    boxes.append(mat("water", (0, (deep + surface) / 2, 0), (rx1 - rx0, surface - deep, rz1 - rz0)))
    # A ramp down each canyon wall, flush against it, 60 m long (18 degrees): the west one from
    # the floor at z 80 up to the rim at z 20, the east one from z -80 up to z -20.
    boxes.append(ramp_z(-half_gap + 3.0, 80.0, 0.0, 20.0, rim, 6.0, rock, material="rock"))
    boxes.append(ramp_z(half_gap - 3.0, -80.0, 0.0, -20.0, rim, 6.0, rock, material="rock"))

    # The crossings. A road bridge at z 0; a 1.2 m balance beam at z -60; and at z 60 a broken
    # bridge, its west half rising 3 m to a lip 12 m short of the east half: a jump for a buggy.
    boxes.append(box((0, rim - 0.4, 0), (2 * half_gap, 0.8, 8.0), "#7d8189", material="concrete"))
    for side in (-1, 1):
        boxes.append(box((0, rim + 0.5, side * 3.8), (2 * half_gap, 1.0, 0.4), "#5a5d63", material="metal"))
    boxes.append(box((0, rim - 0.3, -60.0), (2 * half_gap, 0.6, 1.2), "#7b5a3a", material="wood"))
    boxes.append(bridge((-half_gap, rim, 60.0), (-6.0, rim + 3.0, 60.0), 6.0, "#7d8189", material="concrete"))
    boxes.append(box((13.0, rim - 0.4, 60.0), (14.0, 0.8, 6.0), "#7d8189", material="concrete"))

    # Rocks on the mesas, a metre high (a jump climbs them), and the props: boulders on the
    # rim one push from the edge, barrels on the broken bridge's stubs, buggies on both sides,
    # and balls in the riverbed.
    for at in ((-40, 30), (-55, -45), (-80, 10), (45, -30), (70, 50), (35, 80)):
        boxes.append(box((at[0], rim + 0.5, at[1]), (4.0, 1.0, 3.0), rock, material="rock"))
    for z in (-30.0, -10.0, 30.0):
        props.append(prop("boulder", -half_gap - 2.5, rim, z, loose=True))
        props.append(prop("boulder", half_gap + 2.5, rim, z + 15.0, loose=True))
    for k in range(3):
        props.append(prop("barrel", 10.0 + k * 1.2, rim, 60.0, loose=True))
    for z in (52.0, 68.0):
        props.append(prop("buggy", -45.0, rim, z, yaw=-90.0, loose=True))
    props.append(prop("buggy", 45.0, rim, -10.0, yaw=90.0, loose=True))
    # Beach balls on the canyon floor beside the river (they were in the dry bed, which is water
    # now, and a ball floating off would be a prop that does not stay where the map put it).
    for x, z in ((-10.0, -40.0), (10.0, 10.0), (-10.0, 45.0)):
        props.append(prop("beach_ball", x, 0.0, z, loose=True))
    # Bushes on the mesas, to hide in.
    for at in ((-40.0, -20.0), (-70.0, 60.0), (-90.0, -80.0), (50.0, 20.0), (80.0, -60.0), (60.0, 85.0)):
        boxes.append(bush(at[0], at[1], rim, 3.5, 2.0))
    return doc("pgc_canyon", "Canyon",
               "Two mesas either side of a 40 m canyon: a road bridge, a balance beam, a broken bridge to jump in a buggy, ramps down the walls, and boulders to push in.",
               (-60.0, rim + 1.0, 0.0), -90.0, boxes, declared, props=props)


# --- Harbour ---------------------------------------------------------------------------------

WATER = "#2f5f7a"
QUAY = "#8c8f94"
TIMBER = "#8a6a45"


def boat(cx, cz, w, l, deck_y, floor_y, hull_c, material=None):
    """A hull standing on the basin floor with its deck at deck_y, and a pointed bow toward -Z:
    a square turned 45 degrees about its own centre at the hull's end, half inside the hull."""
    tall = deck_y - floor_y
    s = w / math.sqrt(2.0)
    return [box((cx, floor_y + tall / 2.0, cz), (w, tall, l), hull_c, material=material),
            box((cx, floor_y + tall / 2.0, cz - l / 2.0), (s, tall, s), hull_c, (0, 1, 0, 45.0), material)]


def harbour():
    size, basin = 200.0, -4.0
    # The seabed, dark: the water above it is a real volume now and does the colouring.
    boxes = [box((0, basin - 0.5, 0), (size, 1, size), "#2b3a40", material="sand")]
    boxes += walls(size, 10.0, basin, "#6d7480", "concrete")
    # The water: the whole basin, 3.4 m deep, its surface 0.6 m under the quay's edge. Swum in
    # (dot-player-controller's swim mode), floated on (props lighter than it), climbed out of
    # up the slipways or with a jump at a pier's ladderless edge (0.6 m, under a jump).
    boxes.append(mat("water", (0, basin + 1.7, -45.0), (size - 2.0, 3.4, 110.0)))
    declared = wall_tops(size, 6.0, "the harbour walls, 6 m over the quay")
    props, wires = [], []

    # The quay, 4 m over the basin floor, along the south; the basin is everything north of
    # z 10, filled with water to 0.6 m under the quay. A mole runs out from the quay's east end
    # to the lighthouse platform.
    boxes.append(box((0, -2, 55), (size, 4, 90), QUAY, material="concrete"))
    boxes.append(box((80, -2, -29), (8, 4, 78), QUAY, material="rock"))
    lx, lz = 80.0, -80.0
    boxes.append(box((lx, -2, lz), (24, 4, 24), QUAY, material="rock"))

    # Two slipways out of the basin, 4 m over 22 (about 10 degrees): the way back up for
    # whoever is thrown in, and for a buggy.
    for sx in (-80.0, 55.0):
        boxes.append(ramp_z(sx, -12.0, basin, 10.0, 0.0, 8.0, "#7d8189", material="concrete"))

    # Three timber piers 50 m out, each with a T-head, on pilings. The decks are 0.4 m slabs
    # with 3.6 m under them, so the basin floor runs underneath.
    piers = (-50.0, -10.0, 30.0)
    for px in piers:
        boxes.append(box((px, -0.2, -15), (6, 0.4, 50), TIMBER, material="wood"))
        boxes.append(box((px, -0.2, -43), (14, 0.4, 6), TIMBER, material="wood"))
        for pz in (5.0, -5.0, -15.0, -25.0, -35.0):
            for side in (-1, 1):
                boxes.append(box((px + side * 2.75, -2.2, pz), (0.5, 3.6, 0.5), "#4a3a2a", material="wood"))
        for side in (-1, 1):
            boxes.append(box((px + side * 6.75, -2.2, -43), (0.5, 3.6, 0.5), "#4a3a2a", material="wood"))
            boxes.append(box((px + side * 2.75, -2.2, -45.25), (0.5, 3.6, 0.5), "#4a3a2a", material="wood"))

    # Boats, frozen hulls on the basin floor. The two small ones lie 1.5 m off a pier's pilings
    # (a gap, not a slot), their decks 1 m under it: a hop down, and a jump back up.
    for cx, cz, colour in ((-56.5, -22.0, "#c25b4a"), (36.5, -10.0, "#3b6ea5")):
        boxes += boat(cx, cz, 4.0, 10.0, -1.0, basin, colour, "wood")
        boxes.append(box((cx, -0.1, cz + 3.0), (2.4, 1.8, 2.5), "#e8e2d0", material="wood"))
    # The freighter along the mole, its deck half a metre under the quay, a gangway onto it,
    # two containers on deck and a bridge house at the stern.
    fx, fz = 69.5, -35.0
    boxes += boat(fx, fz, 10.0, 40.0, -0.5, basin, "#3a3d42", "metal")
    boxes.append(box((fx, -1.0, fz), (10.05, 0.5, 40.05), "#a03a2a", material="metal"))
    boxes.append(bridge((77.0, 0.0, -30.0), (73.5, -0.5, -30.0), 2.5, TIMBER, thickness=0.3, material="wood"))
    boxes.append(box((fx, 2.5, -20.0), (8.0, 6.0, 6.0), "#e8e2d0", material="metal"))
    boxes.append(box((fx, 6.5, -21.0), (2.0, 2.0, 2.0), "#c25b4a", material="metal"))
    declared.append({"min": [fx - 4.0, 5.4, -23.0], "max": [fx + 4.0, 8.0, -17.0], "why": "the freighter's bridge house and funnel"})
    for cx, colour in ((fx - 2.0, "#c2a23a"), (fx + 2.0, "#3f9a96")):
        boxes.append(box((cx, 0.8, -44.0), (2.4, 2.6, 12.0), colour, material="metal"))
        declared.append({"min": [cx - 1.2, 2.0, -50.0], "max": [cx + 1.2, 2.6, -38.0], "why": "a container's top, on the freighter"})

    # The lighthouse: a 6 m core in red and white bands, climbed by a square spiral round it.
    # Each side is a bridge() 3 m up over 6 (27 degrees) between 3 m corner landings; the
    # last loop's three other sides are a gallery at 21 m, 2.5 m over the lane below it.
    rise, top = 3.0, 21.0
    for k in range(8):
        boxes.append(box((lx, k * 3.0 + 1.5, lz), (6, 3, 6), "#e8e2d0" if k % 2 == 0 else "#c25b4a", material="concrete"))
    # The lantern room is glass round a lamp: shot out from the gallery, it leaves the lamp
    # holding up the roof.
    boxes.append(box((lx, 25.25, lz), (2.0, 2.5, 2.0), "#f2e6a0"))
    boxes.append(mat("glass", (lx, 25.25, lz), (6, 2.5, 6)))
    boxes.append(box((lx, 26.75, lz), (6.4, 0.5, 6.4), "#c25b4a", material="metal"))
    declared.append({"min": [lx - 3.2, 26.5, lz - 3.2], "max": [lx + 3.2, 27.5, lz + 3.2], "why": "the lighthouse's roof"})
    corners = [(4.5, 4.5), (-4.5, 4.5), (-4.5, -4.5), (4.5, -4.5)]
    steps = int(top / rise)
    for k in range(1, steps + 1):
        c = corners[k % 4]
        boxes.append(box((lx + c[0], k * rise - 0.25, lz + c[1]), (3, 0.5, 3), "#9aa3ad", material="concrete"))
    for k in range(steps):
        a, b = corners[k % 4], corners[(k + 1) % 4]
        d = ((b[0] - a[0]) / 9.0, (b[1] - a[1]) / 9.0)
        p0 = (lx + a[0] + d[0] * 1.5, k * rise, lz + a[1] + d[1] * 1.5)
        p1 = (lx + b[0] - d[0] * 1.5, (k + 1) * rise, lz + b[1] - d[1] * 1.5)
        boxes.append(bridge(p0, p1, 3.0, "#9aa3ad", material="concrete"))
    for k in range(steps + 1, steps + 4):
        c = corners[k % 4]
        boxes.append(box((lx + c[0], top - 0.25, lz + c[1]), (3, 0.5, 3), "#9aa3ad", material="concrete"))
    for k in range(steps, steps + 3):
        a, b = corners[k % 4], corners[(k + 1) % 4]
        boxes.append(box((lx + (a[0] + b[0]) / 2.0, top - 0.25, lz + (a[1] + b[1]) / 2.0),
                         (6 if a[1] == b[1] else 3, 0.5, 3 if a[1] == b[1] else 6), "#9aa3ad", material="concrete"))

    # Two quay cranes: legs straddling the quay's edge, a gantry, a boom out over the basin and
    # a container hanging off it.
    for cx in (-30.0, 10.0):
        for lzz in (12.0, 20.0):
            for side in (-1, 1):
                boxes.append(box((cx + side * 4.0, 7.0, lzz), (1, 14, 1), "#d4a017", material="metal"))
        boxes.append(box((cx, 14.75, 16.0), (10, 1.5, 10), "#d4a017", material="metal"))
        boxes.append(box((cx, 16.5, 18.0), (4, 2, 4), "#5a5d63", material="metal"))
        boxes.append(box((cx, 15.5, -6.0), (1.5, 1.0, 36.0), "#d4a017", material="metal"))
        boxes.append(box((cx, 10.95, -14.0), (0.1, 8.1, 0.1), "#3a3d42", material="metal"))
        boxes.append(box((cx, 5.6, -14.0), (2.4, 2.6, 6.0), "#a55b3b", material="metal"))
        declared.append({"min": [cx - 5.0, 13.9, -24.0], "max": [cx + 5.0, 18.0, 21.0], "why": "a crane's gantry and boom"})
        declared.append({"min": [cx - 1.2, 6.8, -17.0], "max": [cx + 1.2, 7.6, -11.0], "why": "the container hanging off a crane"})

    # Containers on the quay, one and two high (tops declared).
    cont = ["#a55b3b", "#3f9a96", "#5f9e4f", "#c2a23a"]
    for k, (cx, cz, stack) in enumerate(((48.0, 32.0, 2), (48.0, 36.0, 1), (66.0, 32.0, 1), (66.0, 36.0, 2), (57.0, 50.0, 2))):
        for level in range(stack):
            boxes.append(box((cx, 1.3 + level * 2.6, cz), (12.0, 2.6, 2.4), cont[(k + level) % 4], material="metal"))
        declared.append({"min": [cx - 6.0, 2.5, cz - 1.2], "max": [cx + 6.0, 2.6 * stack + 1.0, cz + 1.2], "why": "a container's top"})

    # The harbour master's office, its door on a button either side.
    office, door_at, door_yaw, inward = building(-70.0, 40.0, 12.0, 9.0, 4.0, "s", "#e8e2d0", material="concrete",
                                                 windows=("n", "e", "w"), roof_material="concrete")
    boxes += office
    n = len(props)
    props.append(prop("door", door_at[0], 0.0, door_at[1], yaw=door_yaw))
    props.append(prop("button", door_at[0] + 1.9, 0.0, door_at[1] - inward[1] * 0.33, lift=1.0))
    props.append(prop("button", door_at[0] - 1.9, 0.0, door_at[1] + inward[1] * 0.33, lift=1.0))
    wires.append(wire(n + 1, "pressed", n, "toggle"))
    wires.append(wire(n + 2, "pressed", n, "toggle"))
    declared.append({"min": [-76.0, 4.0, 35.5], "max": [-64.0, 5.0, 44.5], "why": "the office roof"})

    # Bollards along the quay's edge (0.6 m: a hop), clear of the piers, slipways, mole and
    # crane legs; lamps further back.
    for x in range(-90, 95, 10):
        if any(abs(x - p) < 6 for p in piers) or any(abs(x - s) < 7 for s in (-80, 55)) \
                or any(abs(x - c) < 7 for c in (-30, 10)) or 72 <= x <= 88:
            continue
        boxes.append(box((x, 0.3, 10.8), (0.4, 0.6, 0.4), "#3a3d42", material="metal"))
    for x in range(-90, 91, 20):
        b, dcl = lamp(float(x), 26.0)
        boxes += b
        declared += dcl

    # Props: buggies on the quay, cargo on the piers and the freighter, barrels up on the
    # lighthouse gallery to throw off it, and balls in the basin.
    for x in (-20.0, 20.0):
        props.append(prop("buggy", x, 0.0, 60.0, loose=True))
    for k in range(6):
        props.append(prop("crate", -12.0 + (k % 3) * 1.05, (k // 3) * 1.0, -42.0, loose=True))
    for k in range(4):
        props.append(prop("barrel", -54.0 + k * 1.2, 0.0, -44.0, loose=True))
    for k in range(5):
        props.append(prop("crate", fx - 2.0 + (k % 2) * 1.05, -0.5 + (k // 2) * 1.0, -30.0, loose=True, tint="#c2a23a"))
    for k in range(3):
        props.append(prop("barrel", lx - 4.5, top, lz - 1.5 + k * 1.5, loose=True))
    for k in range(4):
        props.append(prop("plank", 30.0, k * 0.15, 4.0, loose=True))
    # Floating on the surface, not on the bed: game-playground's buoyancy launched a beach ball
    # put down under 3.4 m of water two kilometres into the air (tools/map_props.gd, 2026-10-07).
    for at in ((-30.0, -60.0), (10.0, -70.0), (45.0, -50.0), (-75.0, -30.0)):
        props.append(prop("beach_ball", at[0], basin + 3.4, at[1], loose=True))
    props.append(prop("crate_large", lx - 8.0, 0.0, lz + 8.0, loose=True))
    return doc("pgc_harbour", "Harbour",
               "Three piers over a sunken basin with slipways out, boats to jump onto, quay cranes, a freighter, and a lighthouse climbed by a spiral to throw things off.",
               (0, 1, 40), 0.0, boxes, declared, props=props, wires=wires)


# --- Fling Bowl ------------------------------------------------------------------------------

def _yawed(yaw, axial0, axial1, width, y0, y1, colour, material=None):
    """An upright box whose local Z runs from axial0 to axial1 along the direction yaw (radians)."""
    mid = (axial0 + axial1) / 2.0
    return box((math.sin(yaw) * mid, (y0 + y1) / 2.0, math.cos(yaw) * mid), (width, y1 - y0, axial1 - axial0),
               colour, (0, 1, 0, math.degrees(yaw)), material)


ICE_FACETS = (6, 18)


def bowl(facet_extra=2.0):
    sides, flat, rim_r, outer, h = 24, 14.0, 40.0, 48.0, 15.0
    boxes = [box((0, -0.5, 0), (2 * (flat + 2), 1, 2 * (flat + 2)), "#d9c27a", material="sand")]
    declared = []
    props = []
    half = math.pi / sides
    slope = math.atan2(h, rim_r - flat)
    # The bowl is a frustum of a 24-sided pyramid: one bridge() per side, from the flat centre's
    # edge up to the rim. Each is as wide as its side at the rim, so neighbours overlap toward
    # the middle; where they do, the one whose own axis is nearer is the higher, so the visible
    # surface is exactly the facet and the seams meet with no lip and no gap. Each slab is thick
    # enough that its underside is below the ground even at the rim: no hollow under the bowl.
    thick = h * math.cos(slope) + 0.3
    for k in range(sides):
        yaw = 2.0 * math.pi * k / sides
        d = (math.sin(yaw), math.cos(yaw))
        # 2 m wider still (hidden under the neighbours either way): the survey reads a tilted
        # box as its world AABB, and at +0.1 to +1.0 the AABBs of two facets some way apart, or
        # of a facet and a rim block, came 0.06-0.65 m apart, which it calls a slot. Anything
        # from +1.2 up clears every pair; 2 leaves a margin.
        width = 2.0 * rim_r * math.tan(half) + facet_extra
        boxes.append(bridge((d[0] * flat, 0.0, d[1] * flat), (d[0] * rim_r, h, d[1] * rim_r), width,
                            "#3b6ea5" if k % 2 == 0 else "#e8e2d0", thickness=thick, material="concrete"))
        # Two ice chutes facing each other across the bowl (east and west): a 3.6 m lane of ice
        # 0.1 m thick laid on the facet (a step at each end), which nothing climbs and which
        # brings whatever goes down it to the floor with its speed. A lane and not an ice facet:
        # ice is see-through, and a whole facet of it showed the overlapping slabs inside it.
        if k in ICE_FACETS:
            lift = 0.1 / math.cos(slope)
            boxes.append(bridge((d[0] * flat, lift, d[1] * flat), (d[0] * rim_r, h + lift, d[1] * rim_r), 3.6,
                                None, thickness=0.1, material="ice"))
    # The rim: an 8 m walkway at 15 m on solid blocks, with a 1.5 m parapet round its outside.
    for k in range(sides):
        yaw = 2.0 * math.pi * k / sides
        width = 2.0 * outer * math.tan(half) + 0.1
        boxes.append(_yawed(yaw, rim_r, outer, width, -1.0, h, "platform", "concrete"))
        boxes.append(_yawed(yaw, outer - 1.0, outer, width, h, h + 1.5, "#c25b4a", "concrete"))
        c = (math.sin(yaw) * (outer - 0.5), math.cos(yaw) * (outer - 0.5))
        reach = width / 2.0 + 0.5
        declared.append({"min": [r(c[0] - reach), h + 1.3, r(c[1] - reach)], "max": [r(c[0] + reach), h + 2.0, r(c[1] + reach)],
                         "why": "the parapet's top, 1.5 m over the rim"})
    # A pedestal in the middle (an octagon, 1 m: a jump climbs it), and a diving board off the
    # north rim, 8 m out over the slope, to be thrown from.
    # The pedestal is rubber: a jump off it goes 1.8 times as high.
    boxes.append(box((0, 0.5, 0), (6, 1.0, 6), "#c25b4a", material="rubber"))
    boxes.append(box((0, 0.5, 0), (6, 1.0, 6), "#c25b4a", (0, 1, 0, 45.0), "rubber"))
    boxes.append(box((0, h - 0.2, -(rim_r - 3.5)), (2.5, 0.4, 9.0), "#c2a23a", material="wood"))

    # Boulders and balls round the rim to roll in, sleds to ride down, beach balls and a buggy
    # in the middle, crates on the pedestal.
    for k in range(8):
        yaw = 2.0 * math.pi * (k + 0.5) / 8.0
        rr = rim_r + 2.5
        props.append(prop("boulder", math.sin(yaw) * rr, h, math.cos(yaw) * rr, loose=True))
    for k in range(8):
        yaw = 2.0 * math.pi * k / 8.0 + 0.2
        rr = rim_r + 3.0
        props.append(prop("ball", math.sin(yaw) * rr, h, math.cos(yaw) * rr, loose=True, tint="#e0702a"))
    for k in range(4):
        yaw = 2.0 * math.pi * k / 4.0 + 0.45
        rr = rim_r + 2.0
        props.append(prop("plank", math.sin(yaw) * rr, h, math.cos(yaw) * rr, yaw=math.degrees(yaw), loose=True,
                          tint="#e0a052", physics={"gravity": True, "weight": 1.0, "friction": 0.05, "bounce": 0.0}))
    for at in ((-8.0, 6.0), (8.0, 6.0), (0.0, -9.0)):
        props.append(prop("beach_ball", at[0], 0.0, at[1], loose=True))
    for k in range(3):
        props.append(prop("crate", -1.05 + k * 1.05, 1.0, 0.0, loose=True))
    props.append(prop("crate", 0.0, 2.0, 0.0, loose=True))
    props.append(prop("buggy", 8.0, 0.0, -6.0, yaw=90.0, loose=True))
    return doc("pgc_bowl", "Fling Bowl",
               "A 96 m bowl with 30-degree sides, a rim walkway with boulders to roll in, sleds to ride down, a pedestal in the middle and a diving board to be thrown off.",
               (0, h + 1.0, 44.0), 0.0, boxes, declared, props=props)


# --- Obstacle Park ---------------------------------------------------------------------------

def obstacle():
    size, wall_h = 160.0, 6.0
    # A splash pool under the balance beam is a hole in the grass, 2 m deep: a fall off the beam
    # is a swim now, and steps at its north end climb out to the stones.
    pool = (-2.5, 5.5, 0.0, 13.5)
    boxes = slab_with_holes(-size / 2, size / 2, -size / 2, size / 2, 0.0, 3.0, [pool], material="grass")
    boxes += walls(size, wall_h, colour="#6d7480", material="concrete")
    declared = wall_tops(size, wall_h, "the outer walls, 6 m up")
    props, wires = [], []
    shades = ["#3b6ea5", "#3f9a96", "#5f9e4f", "#c2a23a", "#a55b3b", "#8d5fa8"]

    # Jumps are sized to the player: a running jump clears 4.75 m level, 3.68 m rising 0.8 and
    # 3.23 m rising 1.0, and climbs 1.035 m at most. Nothing here asks for more than 2.5 m.
    # Every surface the course is run on is concrete or wood, which move a player exactly as the
    # boxes did before they had a material (no drag), so the measured jumps below still hold.
    boxes.append(box((0, 0.1, 60), (10, 0.2, 10), "start", material="concrete"))
    # 1. The steps: four 1 m risers, each a jump.
    for k in range(4):
        boxes.append(box((0, (k + 1) / 2.0, 52.0 - 3.0 * k), (6, k + 1.0, 3), shades[k], material="concrete"))
    # 2. Stepping stones at 4 m, 2 m square, 2.5 m apart, in a zigzag.
    for j in range(6):
        boxes.append(box((-1.5 if j % 2 == 0 else 1.5, 2.0, 38.0 - 4.5 * j), (2, 4, 2), shades[j % 6], material="concrete"))
    # 3. A 0.8 m balance beam, 12 m long, onto a landing, over the splash pool: its posts stand
    # on the pool's bed, the second at z 8 rather than 10, where it stood 0.3 m off a step's face
    # (a slot, the survey said).
    px0, px1, pz0, pz1 = pool
    pool_bed = -2.0
    boxes.append(box((1.5, 3.8, 6.0), (0.8, 0.4, 12.0), "#c2a23a", material="wood"))
    for z in (2.0, 8.0):
        boxes.append(box((1.5, (3.6 + pool_bed) / 2.0, z), (0.4, 3.6 - pool_bed, 0.4), "#3a3d42", material="metal"))
    boxes.append(box((0.5, 2.0, -3.0), (6, 4, 6), "platform", material="concrete"))
    boxes.append(mat("sand", ((px0 + px1) / 2, pool_bed - 0.5, (pz0 + pz1) / 2), (px1 - px0, 1.0, pz1 - pz0)))
    boxes += pit_steps("z", pz1, -1, px0, px1, 0.0, pool_bed, "concrete")
    boxes.append(mat("water", ((px0 + px1) / 2, (pool_bed - 0.3) / 2, (pz0 + pz1) / 2), (px1 - px0, 1.7, pz1 - pz0)))
    # 4. The climb: five blocks west, each 0.8 m higher, 2 m apart. The landing is 6 m wide so
    # there are 4 m to turn and run in off the beam: at 4 m wide a bot driving the course missed
    # the first block every time on its first try (2.0 m gap and 1.5 m alike), short of speed.
    for i in range(5):
        top = 4.8 + 0.8 * i
        boxes.append(box((-6.0 - 5.0 * i, top / 2.0, -3.0), (3, top, 3), shades[(i + 1) % 6], material="concrete"))
    # 5. The gate: a platform at 8 m with a wall across it, through a door on a button.
    gx, gz, gy = -35.5, -3.0, 8.0
    boxes.append(box((gx, gy / 2.0, gz), (10, gy, 10), "platform", material="concrete"))
    for z0, z1 in ((-8.0, -4.2), (-1.8, 2.0)):
        boxes.append(box((gx, gy + 1.5, (z0 + z1) / 2.0), (0.4, 3.0, z1 - z0), "#c25b4a", material="concrete"))
    boxes.append(box((gx, gy + 2.9, gz), (0.4, 0.2, 2.4), "#c25b4a", material="concrete"))
    declared.append({"min": [gx - 0.3, gy + 2.8, -8.0], "max": [gx + 0.3, gy + 3.5, 2.0], "why": "the gate wall's top"})
    n = len(props)
    props.append(prop("door", gx, gy, gz, yaw=90.0))
    props.append(prop("button", gx + 0.33, gy, gz + 1.9, yaw=90.0, lift=1.0))
    props.append(prop("button", gx - 0.33, gy, gz - 1.9, yaw=90.0, lift=1.0))
    wires.append(wire(n + 1, "pressed", n, "toggle"))
    wires.append(wire(n + 2, "pressed", n, "toggle"))
    # 6. The tower: an 8 m core 20 m tall, climbed by fifteen ledges spiralling round it, each
    # 0.8 m over the last and 2.25 m from it; a loop is 6.4 m, so there is headroom under every
    # ledge. The last is level with the top: the deck to be thrown from.
    tx, tz, top = -50.0, -3.0, 20.0
    for k in range(5):
        boxes.append(box((tx, k * 4.0 + 2.0, tz), (8, 4, 8), "#e8e2d0" if k % 2 == 0 else "#9aa3ad", material="concrete"))
    ring = [(5.75, 0.0), (5.75, 5.75), (0.0, 5.75), (-5.75, 5.75), (-5.75, 0.0), (-5.75, -5.75), (0.0, -5.75), (5.75, -5.75)]
    for k in range(15):
        o = ring[k % 8]
        boxes.append(box((tx + o[0], 8.8 + 0.8 * k - 0.25, tz + o[1]), (3.5, 0.5, 3.5), shades[k % 6], material="concrete"))
    boxes.append(box((tx + 3.0, top + 2.0, tz + 3.0), (0.2, 4.0, 0.2), "#3a3d42"))
    boxes.append(box((tx + 3.0, top + 3.4, tz + 2.2), (0.1, 1.0, 1.4), "#c25b4a"))
    declared.append({"min": [tx + 2.8, top + 2.8, tz + 1.4], "max": [tx + 3.2, top + 4.5, tz + 3.2], "why": "the flag on the tower"})
    # A sand pit round the tower's foot, where the thrown land.
    boxes.append(box((tx, 0.01, tz), (40, 0.02, 40), "#d9c27a", material="sand"))

    # The vault by the start: shut, and opened by the button on top of the tower.
    vault, door_at, door_yaw, inward = building(25.0, 50.0, 10.0, 8.0, 4.0, "w", "#8d5fa8", material="concrete", roof_material="concrete")
    boxes += vault
    declared.append({"min": [20.0, 4.0, 46.0], "max": [30.0, 5.0, 54.0], "why": "the vault's roof"})
    n = len(props)
    props.append(prop("door", door_at[0], 0.0, door_at[1], yaw=door_yaw))
    props.append(prop("button", tx - 2.0, top, tz - 2.0, lift=0.0))
    wires.append(wire(n + 1, "pressed", n, "toggle"))
    for k in range(3):
        props.append(prop("beach_ball", 23.0 + k * 0.0, 0.0, 47.5 + k * 2.5, loose=True))
    props.append(prop("die", 28.0, 0.0, 48.0, loose=True, scale=2.0))
    props.append(prop("crate", 28.0, 0.0, 52.0, loose=True, tint="#c2a23a"))

    # Trees round the field, crates and balls to throw from the tower, buggies by the start.
    for at in ((40.0, -40.0), (-60.0, 50.0), (60.0, 10.0), (-10.0, -50.0), (55.0, -65.0), (-65.0, -55.0)):
        b, dcl = tree(at[0], at[1])
        boxes += b
        declared += dcl
    for k in range(3):
        props.append(prop("crate", tx + 1.5 - k * 1.05, top, tz + 1.0, loose=True))
    props.append(prop("ball", tx - 2.0, top, tz + 2.0, loose=True, tint="#e0702a"))
    for x in (12.0, 18.0):
        props.append(prop("buggy", x, 0.0, 68.0, loose=True))
    for k in range(6):
        props.append(prop("crate", -12.0 + (k % 3) * 1.05, (k // 3) * 1.0, 62.0, loose=True))
    # Two trampolines by the start, and bushes round the field to hide in.
    for at in ((10.0, 30.0), (15.0, 35.0)):
        boxes.append(trampoline(at[0], at[1]))
    for at in ((30.0, 10.0), (45.0, -20.0), (-20.0, 40.0), (-70.0, 20.0), (20.0, -60.0), (62.0, 40.0)):
        boxes.append(bush(at[0], at[1]))
    return doc("pgc_obstacle", "Obstacle Park",
               "A course of steps, stepping stones, a balance beam and a climb to a gate on a button, then a tower of spiral ledges to a deck to be thrown from, whose button opens a vault.",
               (0, 1, 60), 0.0, boxes, declared, props=props, wires=wires)


# --- Nature --------------------------------------------------------------------------------

def nature():
    size, wall_h = 220.0, 6.0
    boxes = [mat("grass", (0, -0.5, 0), (size, 1, size))]
    boxes += walls(size, wall_h, colour="#6b6f4e")
    declared = wall_tops(size, wall_h, "the outer walls, 6 m up")
    props, wires = [], []

    # A snow field in the north-west with an ice rink on it, both a step high.
    boxes.append(mat("snow", (-55, 0.05, -50), (60, 0.1, 50)))
    boxes.append(mat("ice", (-55, 0.15, -50), (30, 0.1, 20)))
    for k in range(4):
        props.append(prop("crate", -62 + k * 4.0, 0.2, -50, loose=True))

    # A mud pit in the middle, sunk in nothing: a 0.1 m layer that slows whoever crosses it.
    boxes.append(mat("mud", (0, 0.05, -10), (24, 0.1, 18)))

    # A beach of sand in the east, sloping gently into a pond held in by a stone rim. The water
    # is a volume from the pond's bed to 0.2 m under the rim: walked into for now.
    boxes.append(mat("sand", (60, 0.05, 20), (50, 0.1, 40)))
    px, pz, pw, pd, rim = 60.0, 50.0, 36.0, 24.0, 1.4
    for side in (-1, 1):
        boxes.append(mat("rock", (px + side * (pw / 2 + 0.5), rim / 2, pz), (1.0, rim, pd + 2.0)))
        boxes.append(mat("rock", (px, rim / 2, pz + side * (pd / 2 + 0.5)), (pw, rim, 1.0)))
    boxes.append(mat("sand", (px, 0.05, pz), (pw, 0.1, pd)))
    boxes.append(mat("water", (px, (0.1 + rim - 0.2) / 2 + 0.05, pz), (pw, rim - 0.3, pd)))
    # Steps over the rim on the beach side, in and out.
    # Over the rim by a 3 m landing on top of it, a ramp each side: two ramps meeting the rim
    # straight left 0.7 m between them and it, which the survey called a slot.
    edge = pz - pd / 2 - 0.5
    boxes.append(mat("rock", (px, rim / 2, edge), (4.0, rim, 3.0)))
    boxes.append(ramp_z(px, edge - 1.5 - 4.5, 0.1, edge - 1.5, rim, 4.0, "#8a7a62"))
    boxes.append(ramp_z(px, edge + 1.5 + 4.5, 0.1, edge + 1.5, rim, 4.0, "#8a7a62"))
    # Floating where they float (a barrel 0.05 m in, a beach ball on top), not on the bed: put down
    # under the water, game-playground's buoyancy threw them tens and hundreds of metres up.
    surface = (0.1 + rim - 0.2) / 2 + 0.05 + (rim - 0.3) / 2
    for k in range(3):
        props.append(prop("barrel", px - 8 + k * 6, surface - 0.05, pz + 4, loose=True))
        props.append(prop("beach_ball", px - 5 + k * 6, surface, pz - 5, loose=True))

    # A lava pit in the south-west, rimmed in rock with a narrow rock bridge across it.
    lx, lz, lw, ld, lrim = -50.0, 50.0, 18.0, 18.0, 1.0
    for side in (-1, 1):
        boxes.append(mat("rock", (lx + side * (lw / 2 + 0.75), lrim / 2, lz), (1.5, lrim, ld + 3.0)))
        boxes.append(mat("rock", (lx, lrim / 2, lz + side * (ld / 2 + 0.75)), (lw, lrim, 1.5)))
    boxes.append(mat("rock", (lx, -0.25, lz), (lw, 0.5, ld)))
    boxes.append(mat("lava", (lx, 0.3, lz), (lw, 0.6, ld)))
    boxes.append(mat("rock", (lx, lrim - 0.25, lz), (lw + 3.0, 0.5, 1.5)))
    # Up to the bridge's west end, flush with it (0.25 m short was a slot).
    boxes.append(ramp_z(lx - lw / 2 - 2.5, lz - 6.0, 0.0, lz - 0.75, lrim, 2.0, "#5a5752"))
    boxes.append(ramp_z(lx - lw / 2 - 2.5, lz + 6.0, 0.0, lz + 0.75, lrim, 2.0, "#5a5752"))
    for k in range(3):
        props.append(prop("crate", lx + lw / 2 + 4.0, 0.0, lz - 4 + k * 4, loose=True))

    # Rubber trampolines on the meadow, 0.3 m pads.
    for k, at in enumerate(((-15, 30), (-5, 34), (5, 30))):
        boxes.append(mat("rubber", (at[0], 0.15, at[1]), (4.0, 0.3, 4.0)))

    # A rock outcrop to climb in the north-east, and a wooden lookout on it.
    boxes.append(mat("rock", (55, 2.0, -50), (20, 4.0, 16)))
    boxes.append(ramp_z(55, -50 + 8 + 12, 0.0, -50 + 8, 4.0, 6.0, "#5a5752"))
    boxes.append(mat("wood", (55, 4.15, -50), (6, 0.3, 6)))

    # A greenhouse of glass on a wooden frame, south of the mud: a doorway in the south wall.
    gx, gz, gw, gd, gh = 0.0, 50.0, 16.0, 10.0, 3.5
    for side in (-1, 1):
        boxes.append(mat("glass", (gx + side * (gw / 2 - 0.05), gh / 2, gz), (0.1, gh, gd)))
    boxes.append(mat("glass", (gx, gh / 2, gz - gd / 2 + 0.05), (gw, gh, 0.1)))
    for side in (-1, 1):
        boxes.append(mat("glass", (gx + side * (gw / 4 + 0.75), gh / 2, gz + gd / 2 - 0.05), (gw / 2 - 1.5, gh, 0.1)))
    boxes.append(mat("glass", (gx, gh + 0.05, gz), (gw, 0.1, gd)))
    for cx_ in (-gw / 2, 0.0, gw / 2):
        for cz_ in (-gd / 2, gd / 2):
            boxes.append(mat("wood", (gx + cx_, gh / 2, gz + cz_), (0.2, gh, 0.2)))
    declared.append({"min": [gx - gw / 2, gh, gz - gd / 2], "max": [gx + gw / 2, gh + 0.6, gz + gd / 2], "why": "the greenhouse's glass roof"})
    for k in range(4):
        props.append(prop("crate", gx - 5 + k * 3, 0.0, gz, loose=True, tint="#5f9e4f"))

    # A frozen lake in the north: deep water under a sheet of thin ice, in a 2 m stone basin, and
    # a diving board on a wooden tower over it. The ice holds a walker; a drop off the board is
    # 3 m, fast enough to go through (game-playground breaks thin ice like glass, from impacts).
    fx, fz, fw, fd, frim = 10.0, -80.0, 24.0, 16.0, 2.0
    for side in (-1, 1):
        boxes.append(mat("rock", (fx + side * (fw / 2 + 0.5), frim / 2, fz), (1.0, frim, fd + 2.0)))
        boxes.append(mat("rock", (fx, frim / 2, fz + side * (fd / 2 + 0.5)), (fw, frim, 1.0)))
    boxes.append(mat("water", (fx, (0.1 + frim - 0.15) / 2, fz), (fw, frim - 0.25, fd)))
    boxes.append(mat("thin_ice", (fx, frim - 0.1, fz), (fw, 0.1, fd)))
    boxes.append(ramp_z(fx, fz + fd / 2 + 1.0 + 10.0, 0.0, fz + fd / 2 + 1.0, frim, 4.0, "#8a7a62"))
    tx = fx + fw / 2 + 1.0 + 1.5
    boxes.append(mat("wood", (tx, 2.5, fz), (3.0, 5.0, 3.0)))
    boxes.append(ramp_z(tx, fz + 1.5 + 13.0, 0.0, fz + 1.5, 5.0, 3.0, "#7b5a3a"))
    boxes.append(mat("wood", (tx - 3.5, 4.9, fz), (4.0, 0.2, 1.0)))
    declared.append({"min": [fx - fw / 2, 0.0, fz - fd / 2], "max": [fx + fw / 2, frim - 0.15, fz + fd / 2],
                     "why": "the lake's bed, under the ice until somebody breaks it"})

    # A slime swamp on the west edge: a shallow toxic pool in a low rim, stepping stones across.
    wx, wz, ww, wd, wrim = -95.0, 10.0, 16.0, 24.0, 0.8
    for side in (-1, 1):
        boxes.append(mat("rock", (wx + side * (ww / 2 + 0.5), wrim / 2, wz), (1.0, wrim, wd + 2.0)))
        boxes.append(mat("rock", (wx, wrim / 2, wz + side * (wd / 2 + 0.5)), (ww, wrim, 1.0)))
    boxes.append(mat("mud", (wx, 0.05, wz), (ww, 0.1, wd)))
    boxes.append(mat("slime", (wx, 0.4, wz), (ww, 0.6, wd)))
    for k in range(6):
        boxes.append(mat("rock", (wx + (-3.0 if k % 2 else 3.0), 0.45, wz - 10.0 + k * 4.0), (2.0, 0.9, 2.0)))

    # Bushes to hide in round the meadow: foliage, walked through.
    for at in ((-32, 30), (32, 26), (-36, -12), (40, -18), (16, 62), (-22, 62), (-5, 15), (28, 75)):
        boxes.append(mat("foliage", (at[0], 1.0, at[1]), (3.0, 2.0, 3.0)))

    # Trees round the meadow.
    for at in ((-20, 0), (20, 0), (-25, 70), (25, 70), (90, -20), (-75, 42), (30, -100), (-30, -85)):
        b, dcl = tree(at[0], at[1])
        boxes += b
        declared += dcl
    props.append(prop("buggy", 20, 0.0, 40, loose=True))
    return doc("pgc_nature", "Nature",
               "A meadow with a snow field and an ice rink, a mud pit, a sand beach and a pond, a lava pit with a rock bridge, a frozen lake with a diving board, a slime swamp, bushes, trampolines, a rock outcrop and a glass greenhouse.",
               (0, 1, 80), 0.0, boxes, declared, props=props, wires=wires)


def main():
    check = "--check" in sys.argv
    MAPS.mkdir(exist_ok=True)
    bad = 0
    for d in (plots(), quarry(), slopes(), town(), islands(), site(), warehouse(), canyon(), harbour(), bowl(), obstacle(), nature()):
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
