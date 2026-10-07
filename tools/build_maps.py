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


def doc(id_, name, blurb, spawn, spawn_yaw, boxes, declared, tier=1):
    return {
        "format": 1, "kind": "playground_map", "id": id_, "name": name, "blurb": blurb,
        "map_kind": "sandbox", "tier": tier, "author": AUTHOR,
        "spawn": [r(c) for c in spawn], "spawn_yaw": spawn_yaw,
        "boxes": boxes, "declared": declared,
    }


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
    return doc("pgc_plots", "Build Plots",
               "Eight plots round a spawn plaza, a claim pad in front of each, and a deck to look down on them from.",
               (0, 1, 0), 0.0, boxes, declared)


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
    return doc("pgc_quarry", "Quarry",
               "A pit in two terraces with ramps between them, rails and a cart: a place to throw rocks into.",
               (0, 1, 60), 0.0, boxes, declared)


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
    return doc("pgc_slopes", "Slide Hill",
               "A hill to a deck 20 m up with a pen on top to be thrown from, a far slope that props slide down once their friction is turned down, and a halfpipe.",
               (0, 1, 80), 0.0, boxes, declared)


def main():
    check = "--check" in sys.argv
    MAPS.mkdir(exist_ok=True)
    bad = 0
    for d in (plots(), quarry(), slopes()):
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
