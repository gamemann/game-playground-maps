#!/usr/bin/env python3
"""Read a Source VBSP (v19/v20) far enough to get geometry and zones out of it.

Point it at a surf or bhop map in the genre's usual format and it writes an .obj of the
world geometry and a .json of the entities that become timer zones and spawns.

    tools/bsp_read.py ../inspirations/g2gfast/surf_kitsune.bsp out/

Why this is only a reader and not an importer: what a *map* is here is a
`G2GMap` subclass with `_build()` and `timer_zones()` (see maps/surf_g2g_intro.gd),
and the interesting decisions -- which volume is the START, which of thirty
materials is a ramp, what a stage is -- are judgement calls that differ per map.
Those belong in a hand-written map script that reads this output, not in a
converter guessing at them.

[b]Units.[/b] Source stores map coordinates in the same units this game is
authored in -- `G2GUnits.METRES_PER_UNIT` is 0.01905, which is the Source ratio of
0.75 inch per unit -- so nothing is scaled here. Only the axes are swapped, because
Source is Z-up and Godot is Y-up:

    godot = (src.x, src.z, -src.y)

Emitting metres instead would be the obvious alternative and is wrong: every other
number in this project (`fallback_spawn_units`, `zone_box`, every tunable) is in
genre units, and a map file that mixed the two is a map file nobody can read.
Multiply by `G2GUnits.METRES_PER_UNIT` at the same single boundary everything else
does.
"""

import collections
import json
import lzma
import os
import re
import struct
import sys

# Surface flags worth skipping. Tool textures are not geometry a player touches:
# they are the compiler's own annotations and drawing them buries the map in boxes.
SURF_SKY2D, SURF_SKY, SURF_TRIGGER, SURF_NODRAW = 0x2, 0x4, 0x40, 0x80
SURF_HINT, SURF_SKIP = 0x100, 0x200
SKIP_MASK = SURF_SKY2D | SURF_SKY | SURF_TRIGGER | SURF_NODRAW | SURF_HINT | SURF_SKIP

LUMP_ENTITIES, LUMP_TEXDATA, LUMP_VERTEXES = 0, 2, 3
LUMP_PLANES = 1
LUMP_TEXINFO, LUMP_FACES, LUMP_EDGES, LUMP_SURFEDGES = 6, 7, 12, 13
LUMP_MODELS, LUMP_DISPINFO, LUMP_DISP_VERTS = 14, 26, 33
LUMP_TEXDATA_STRING_DATA, LUMP_TEXDATA_STRING_TABLE = 43, 44
LUMP_NODES, LUMP_LEAFS, LUMP_LEAFBRUSHES = 5, 10, 17
LUMP_BRUSHES, LUMP_BRUSHSIDES = 18, 19

# What a player collides with, which is not what a player can see.
#
# [b]A Source map's solid volume is its brushes, and its drawn faces are only the
# ones that happened to end up visible.[/b] vbsp deletes every face it can prove
# nobody can look at, and a mapper paints the rest with `nodraw` on purpose; on top
# of that a surf map's ride is routinely wrapped in `tools/toolsplayerclip`, which
# is invisible by definition and is the whole reason a ramp is smooth to ride.
# Measured over the eight maps in `inspirations/`, between 31% and 77% of the sides
# of a solid brush are not drawn -- so collision built from the drawn faces is a
# shell with most of itself missing, which is a player falling through a ramp.
#
# These are Source's own values and the mask is its MASK_PLAYERSOLID. GRATE and
# WINDOW are in it because a player cannot walk through a grille or a pane; WATER,
# AREAPORTAL and the MONSTERCLIP that is not also PLAYERCLIP are not, because a
# player walks through all three.
CONTENTS_SOLID, CONTENTS_WINDOW, CONTENTS_GRATE = 0x1, 0x2, 0x8
CONTENTS_MOVEABLE, CONTENTS_PLAYERCLIP = 0x4000, 0x10000
CONTENTS_MONSTER, CONTENTS_LADDER = 0x2000000, 0x20000000
MASK_PLAYERSOLID = (CONTENTS_SOLID | CONTENTS_WINDOW | CONTENTS_GRATE
                    | CONTENTS_MOVEABLE | CONTENTS_PLAYERCLIP | CONTENTS_MONSTER)

# Which brush entities are solid, by classname, because their contents cannot say.
#
# [b]A `trigger_teleport`'s brushes carry CONTENTS_SOLID.[/b] 186 of them do in
# surf_beginner2 and 126 in Surf_Mesa -- the pits, which is the one volume in a surf
# map that must not be solid -- and so do `func_illusionary` and `func_dustcloud`.
# Source never asks the contents alone: it asks the entity what it is. So does this.
# An entity whose classname is in neither list is skipped and said out loud, because
# the alternative to a note is a map with an invisible wall nobody can explain.
SOLID_BRUSH_ENTITIES = frozenset("""
    func_brush func_wall func_wall_toggle func_detail func_breakable
    func_breakable_surf func_button func_rot_button func_door func_door_rotating
    func_movelinear func_water_analog func_conveyor func_train func_tracktrain
    func_tanktrain func_rotating func_platrot func_plat func_lod func_physbox
    func_physbox_multiplayer func_pushable func_monitor func_reflective_glass
    func_clip_vphysics
""".split())

NONSOLID_BRUSH_ENTITIES = frozenset("""
    func_illusionary func_dustcloud func_dustmotes func_smokevolume
    func_precipitation func_areaportal func_areaportalwindow func_occluder
    func_viscluster func_ladder func_bomb_target func_buyzone func_hostage_rescue
    func_nav_blocker func_instance_io_proxy func_fish_pool func_vehicleclip
    trigger_vphysics_motion env_bubbles env_wind func_wall_illusionary
""".split())

# dnode_t and dleaf_t, both 32 bytes in VBSP v20. Every map in `inspirations/` is v20
# and the leaf lump divides by 32 exactly in all eight; v19 carried a
# `CompressedLightCube` inline and measured 56, which is why `model_brushes` checks
# rather than assuming.
FMT_NODE = "<i2i6h2Hh2x"        # planenum, children[2], mins[3], maxs[3], face range, area
FMT_LEAF = "<ihh6h4Hh2x"        # contents, cluster, area/flags, mins/maxs, face and brush ranges
FMT_LEAF_V19 = "<ihh6h4Hh24x2x" # the same plus the 24-byte light cube v20 moved to its own lump, and the 2-byte pad: 56
FMT_BRUSH = "<3i"               # firstside, numsides, contents
FMT_BRUSHSIDE = "<H3h"          # planenum, texinfo, dispinfo, bevel

# dmodel_t is 48 bytes: mins, maxs, origin, headnode, firstface, numfaces.
# Reading it as 9f4i (52) still yields a correct model 0 -- it is the first record
# and every field before the overrun is in place -- and misaligns every model after
# it, so the world renders perfectly while every trigger volume is garbage. That
# cost a pass here; the sizes came out negative, which is the only reason it showed.
FMT_MODEL = "<9f3i"
FMT_FACE = "<HBBihhhh4sifiiiiiHHI"   # 56 bytes, v20
FMT_TEXINFO = "<16f2i"               # 72
FMT_TEXDATA = "<3f5i"                # 32
FMT_DISPVERT = "<3fff"               # 20


class Bsp:
    def __init__(self, path):
        self.path = path
        self.d = open(path, "rb").read()
        ident, self.version = struct.unpack_from("<4si", self.d, 0)
        if ident != b"VBSP":
            raise ValueError("%s is not a VBSP file (magic %r)" % (path, ident))
        self.dir = [struct.unpack_from("<iii4s", self.d, 8 + i * 16)[:3] for i in range(64)]
        self._cache = {}

    def _lump(self, i):
        if i in self._cache:
            return self._cache[i]
        off, ln, _ = self.dir[i]
        raw = self.d[off:off + ln]
        out = decompress_lump(raw)
        self._cache[i] = out
        return out

    def _array(self, i, fmt):
        b, sz = self._lump(i), struct.calcsize(fmt)
        return [struct.unpack_from(fmt, b, o) for o in range(0, len(b) - sz + 1, sz)]

    def load(self):
        # normal(3f), dist(f), type(i). Wanted for exact face normals: a brush face
        # lies on its plane by construction, so deriving a normal from the winding
        # instead is strictly less accurate and flips on a degenerate first triangle.
        self.planes = self._array(LUMP_PLANES, "<4fi")
        self.verts = self._array(LUMP_VERTEXES, "<3f")
        self.edges = self._array(LUMP_EDGES, "<2H")
        self.surfedges = [x[0] for x in self._array(LUMP_SURFEDGES, "<i")]
        self.texinfo = self._array(LUMP_TEXINFO, FMT_TEXINFO)
        self.texdata = self._array(LUMP_TEXDATA, FMT_TEXDATA)
        self.faces = self._array(LUMP_FACES, FMT_FACE)
        self.models = self._array(LUMP_MODELS, FMT_MODEL)
        self.dispinfo = self._lump(LUMP_DISPINFO)
        self.dispverts = self._array(LUMP_DISP_VERTS, FMT_DISPVERT)
        table = [x[0] for x in self._array(LUMP_TEXDATA_STRING_TABLE, "<i")]
        data = self._lump(LUMP_TEXDATA_STRING_DATA)
        # [b]Latin-1, not ASCII.[/b] The string table is the mapper's Windows codepage, and
        # surf_vegetables names its own textures `customs/Früchte/...`: decoded as ASCII the
        # ü became U+FFFD, no pakfile entry matched, and 15% of the map drew the grid with
        # its textures in the pakfile (2026-10-11). Latin-1 maps every byte, and agrees with
        # cp1252 on every letter a material name uses; `read_pak` decodes entry names to match.
        self.texnames = [data[o:data.index(b"\0", o)].decode("latin-1") for o in table]
        self.entities = parse_entities(self._lump(LUMP_ENTITIES).decode("ascii", "replace"))
        self.brushes = self._array(LUMP_BRUSHES, FMT_BRUSH)
        self.brushsides = self._array(LUMP_BRUSHSIDES, FMT_BRUSHSIDE)
        self.leafbrushes = [x[0] for x in self._array(LUMP_LEAFBRUSHES, "<H")]
        self.nodes = self._array(LUMP_NODES, FMT_NODE)
        # v20 leafs are 32 bytes, v19's are 56. Dividing exactly by the wrong one is
        # the failure this file has already paid for once with dmodel_t: every field
        # before the overrun is right, so the first record parses and every record
        # after it is garbage. [b]Chosen by the file's version, not by which size the lump
        # divides by[/b] (2026-10-09): a v19 lump whose leaf count is a multiple of four
        # divides by 32 too, and surf_10x_final's did -- read as v20, every leaf after the
        # first was garbage and so were the brushes reached through them. And the v19
        # format was 54 bytes, two short of the record, which is how a v19 lump that did
        # NOT divide by 32 (surf_greatriver's) failed to import at all.
        raw = len(self._lump(LUMP_LEAFS))
        fmt = FMT_LEAF_V19 if self.version <= 19 else FMT_LEAF
        if raw % struct.calcsize(fmt):
            raise ValueError("leaf lump of %d bytes is neither v19 nor v20 shaped" % raw)
        self.leafs = self._array(LUMP_LEAFS, fmt)
        return self

    # -- faces -----------------------------------------------------------
    def face_material(self, f):
        ti = f[5]
        if ti < 0:
            return "?", 0
        flags, td = int(self.texinfo[ti][16]), int(self.texinfo[ti][17])
        if not 0 <= td < len(self.texdata):
            return "?", flags
        return self.texnames[self.texdata[td][3]], flags

    def face_points(self, f):
        first, n = f[3], f[4]
        pts = []
        for k in range(n):
            se = self.surfedges[first + k]
            e = self.edges[abs(se)]
            pts.append(self.verts[e[0] if se >= 0 else e[1]])
        return pts

    def model_faces(self, model=0):
        m = self.models[model]
        return self.faces[m[10]:m[10] + m[11]]

    def model_bounds(self, model):
        m = self.models[model]
        return (m[0], m[1], m[2]), (m[3], m[4], m[5])

    # -- brushes: the solid volume, as opposed to the visible surface -----
    def model_brushes(self, model=0):
        """Every brush index belonging to one model, by walking its BSP tree.

        [b]There is no per-model brush range to slice.[/b] `dmodel_t` carries a
        headnode and nothing else about brushes; a brush belongs to a model because
        some leaf under that model's node reaches it through the leafbrush table. So
        the tree is walked. Model 0 is the world -- including every `func_detail`,
        which vbsp merged into it -- and models 1..n are one brush entity each.
        """
        out, stack, seen = set(), [self.models[model][9]], set()
        while stack:
            n = stack.pop()
            if n < 0:
                i = -1 - n
                if 0 <= i < len(self.leafs):
                    leaf = self.leafs[i]
                    first, count = leaf[11], leaf[12]
                    out.update(self.leafbrushes[first:first + count])
                continue
            if n >= len(self.nodes) or n in seen:
                continue
            seen.add(n)
            stack.extend(self.nodes[n][1:3])
        return out

    def brush_hull(self, index, epsilon=0.1):
        """One brush as the corner points of its convex hull, in Hammer coordinates.

        A Source brush is stored the way it was authored: as the intersection of the
        half-spaces its sides lie on, with no vertices anywhere. The corners are the
        points where three of those planes meet that no fourth plane excludes, which
        is what this solves -- Cramer's rule over every triple of sides, kept when it
        is inside all the rest.

        [b]Bevel sides are skipped, and must be.[/b] vbsp adds axis-aligned bevel
        planes so that its own AABB sweep has something to test; they are tangent to
        the hull and change none of its corners, and there can be more of them than
        real sides -- Surf_Mesa averages 16.5 sides a brush against roughly 6 real
        ones. Feeding them in costs the cube of that for nothing.

        `epsilon` is Source's own plane tolerance. The planes are float32 and the
        coordinates reach +/-16384, so an exact test drops corners that are on the
        hull by construction, and a hull missing a corner is a solid with a bite out
        of it that a player at 3000 u/s will find.
        """
        first, count, _ = self.brushes[index]
        planes = []
        for s in self.brushsides[first:first + count]:
            if s[3]:                                    # bevel
                continue
            pl = self.planes[s[0]]
            planes.append((pl[0], pl[1], pl[2], pl[3]))
        n = len(planes)
        if n < 4:
            return []
        pts = []
        for i in range(n - 2):
            a = planes[i]
            for j in range(i + 1, n - 1):
                b = planes[j]
                # a x b, reused across the whole inner loop.
                cx = a[1] * b[2] - a[2] * b[1]
                cy = a[2] * b[0] - a[0] * b[2]
                cz = a[0] * b[1] - a[1] * b[0]
                for k in range(j + 1, n):
                    c = planes[k]
                    det = c[0] * cx + c[1] * cy + c[2] * cz
                    if -1e-6 < det < 1e-6:              # the three planes share a line
                        continue
                    # Cramer's rule, with the two remaining cross products inline.
                    bx = b[1] * c[2] - b[2] * c[1]
                    by = b[2] * c[0] - b[0] * c[2]
                    bz = b[0] * c[1] - b[1] * c[0]
                    ax = c[1] * a[2] - c[2] * a[1]
                    ay = c[2] * a[0] - c[0] * a[2]
                    az = c[0] * a[1] - c[1] * a[0]
                    x = (a[3] * bx + b[3] * ax + c[3] * cx) / det
                    y = (a[3] * by + b[3] * ay + c[3] * cy) / det
                    z = (a[3] * bz + b[3] * az + c[3] * cz) / det
                    for p in planes:
                        if p[0] * x + p[1] * y + p[2] * z - p[3] > epsilon:
                            break
                    else:
                        pts.append((round(x, 3), round(y, 3), round(z, 3)))
        # Three planes meeting at one corner produce it once per triple, and a corner
        # where four meet -- every bevelled edge, every wedge tip -- comes out six
        # times. Godot builds its own hull from these, so duplicates are only waste,
        # but a surf map has 2500 brushes and the waste is measured in megabytes.
        return list(dict.fromkeys(pts))

    # -- displacements ---------------------------------------------------
    def displacement_tris(self, f, with_base=False, with_alpha=False):
        """A displacement's subdivided surface.

        The face is the flat quad the mapper drew; the real surface is a
        (2^power + 1) square grid of offsets from it. Ignoring these and drawing
        the quad is the obvious shortcut and it deletes every piece of terrain in
        the map -- 1434 of them in Surf_Mesa, including ramps players ride.

        [b]`with_base` returns each point as `(displaced, flat)`, and the flat one is
        not a curiosity -- it is where a displacement's LIGHTING lives.[/b] A
        displacement's lightmap is parameterised over the quad the mapper drew, not
        over the surface that came out: the luxel extents in the face say so, being
        12x12 or 7x12 on this map's terrain where the grid is always 9x9. So the
        lightmap coordinate has to be projected from the flat point. Projecting the
        displaced one instead sends it off the end of the face's luxel range -- by as
        much as the terrain bulges, which on a cliff is hundreds of units -- where the
        clamp that keeps it inside the atlas parks whole hillsides on a single edge
        luxel. That is not subtle and it is not a seam: two thirds of this map's
        triangles are displacements, and they rendered as smooth bright gradients with
        no shadow in them at all, which read as "the lighting is flat" rather than as
        "the lighting is being sampled in the wrong place".

        `with_alpha` adds a third element, the vertex's blend alpha as 0..1 -- how much of
        a `WorldVertexTransition` material's `$basetexture2` shows there (`dispvert.alpha`
        is 0..255 on disk). It needs `with_base`.
        """
        o = f[6] * 176
        start = struct.unpack_from("<3f", self.dispinfo, o)
        vstart, _tstart, power = struct.unpack_from("<3i", self.dispinfo, o + 12)
        c = self.face_points(f)
        if len(c) != 4:
            return []
        # The grid is laid out from the corner nearest startPosition, which is not
        # necessarily the first vertex of the face winding.
        best = min(range(4), key=lambda k: sum((c[k][a] - start[a]) ** 2 for a in range(3)))
        c = c[best:] + c[:best]
        size = (1 << power) + 1
        grid = []
        for row in range(size):
            t = row / (size - 1)
            lft = [c[0][a] + (c[1][a] - c[0][a]) * t for a in range(3)]
            rgt = [c[3][a] + (c[2][a] - c[3][a]) * t for a in range(3)]
            for col in range(size):
                s = col / (size - 1)
                base = [lft[a] + (rgt[a] - lft[a]) * s for a in range(3)]
                dv = self.dispverts[vstart + row * size + col]
                point = tuple(base[a] + dv[a] * dv[3] for a in range(3))
                if with_alpha:
                    grid.append((point, tuple(base), min(max(dv[4] / 255.0, 0.0), 1.0)))
                else:
                    grid.append((point, tuple(base)) if with_base else point)
        tris = []
        for row in range(size - 1):
            for col in range(size - 1):
                a = row * size + col
                tris.append((grid[a], grid[a + size], grid[a + 1]))
                tris.append((grid[a + 1], grid[a + size], grid[a + size + 1]))
        return tris


def decompress_lump(raw):
    """A lump's bytes, decompressed if the map was compressed.

    [b]Half the surf maps in circulation are LZMA-compressed and nothing says so in
    the header.[/b] `bspzip -repack -compress` -- which every map host runs, because a
    112 MB .bsp is a 112 MB download for every player who joins -- rewrites each lump
    as a `lzma_header_t` followed by a raw LZMA1 stream, and leaves the file's VBSP
    version at 20. So a reader that does not check reads the compressed bytes as
    structures and gets plausible garbage: three of the eight maps here parsed their
    plane array happily and then died in the texture string table, which is simply the
    first lump whose contents are checked against anything.

    The header is `LZMA`, the uncompressed size, the compressed size, and the five
    property bytes that would normally start a .lzma file -- so this is a raw LZMA1
    stream with no end-of-stream marker, which is exactly what FORMAT_RAW plus an
    explicit `max_length` is for. An `.lzma` container reassembled by hand would be
    the other route and needs the same five bytes anyway.
    """
    if len(raw) < 17 or raw[:4] != b"LZMA":
        return raw
    actual, _packed = struct.unpack_from("<II", raw, 4)
    props = raw[12]
    dict_size = struct.unpack_from("<I", raw, 13)[0]
    pb, r = divmod(props, 45)
    lp, lc = divmod(r, 9)
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": max(4096, dict_size),
                "lc": lc, "lp": lp, "pb": pb}]
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
    # No end marker: the stream stops when `actual` bytes have come out of it, and
    # asking for more raises rather than returning what there was.
    return dec.decompress(raw[17:], max_length=actual)


def yaw_to_godot(yaw):
    """A Source yaw as the yaw dot-player-controller builds a forward vector from.

    Source measures yaw anticlockwise about +Z from +X; [method DotFpsMotor.forward]
    is [code](-sin y, 0, -cos y)[/code], and the axis swap has already turned Source's
    +Y into Godot's -Z. Solving the two against each other gives exactly `yaw - 90`,
    and getting it wrong is not visible in any number: the player stands in the right
    place facing the wrong way, which on a map with an obvious route reads as the
    spawn being fine and on a spiral reads as the map being unplayable.
    """
    return float(yaw) - 90.0


def to_godot(p):
    """Source Z-up to Godot Y-up, in genre units. See the module docstring."""
    return (p[0], p[2], -p[1])


def parse_entities(text):
    """The entity lump as one dict per entity.

    [b]An output key repeats, and every repeat is kept.[/b] A trigger that does two
    things on touch carries two `OnTrigger` keys -- bhop_japan's anti-standing blocks
    rename the toucher `default` and then `activator`, in that order -- and a dict that
    kept only the first lost the second: the delay `trap_blocks` reads was never seen,
    and 32 traps imported as nothing. Repeats of an `On*` key are joined with newlines,
    which every reader of outputs already scans with a regex that stops at whitespace.
    Any other key keeps its first value, as before.
    """
    out = []
    for blk in re.findall(r"\{([^{}]*)\}", text):
        kv = {}
        for k, v in re.findall(r'"([^"]*)"\s*"([^"]*)"', blk):
            if k in kv and k.startswith("On"):
                kv[k] += "\n" + v
            else:
                kv.setdefault(k, v)
        if kv:
            out.append(kv)
    return out


def clean_material(m):
    """The base material name.

    VBSP rewrites the name of any face a cubemap patched into
    `maps/<mapname>/<path>_<x>_<y>_<z>`, so the same texture appears under a dozen
    names and grouping by the raw string scatters one surface across the map.

    [b]And a leading `/` is dropped.[/b] A mapper who kept a material in the root of
    `materials/` and typed its path with a slash gets `/SURFACE` in the string table,
    which the engine resolves to `materials/surface.vmt`. Kept, it looked up
    `materials//surface.vmt`, missed, and the surface was drawn in the prototype grid:
    97% of surf_interference's faces and a third of surf_aquaflow's, whose own textures
    were in the pakfile the whole time.
    """
    m = m.lower().replace("\\", "/").lstrip("/")
    # The `_x_y_z` suffix is only vbsp's when vbsp moved the material under `maps/`: a
    # mapper's own `corals_1_5_8_9` ends in three numbers too, and stripping it there
    # turned it into `corals_1`, which does not exist.
    patched = re.sub(r"^maps/[^/]+/", "", m)
    if patched == m:
        return m
    return re.sub(r"_-?\d+_-?\d+_-?\d+$", "", patched)


def write_obj(bsp, out_path):
    groups = collections.defaultdict(list)
    for f in bsp.model_faces(0):
        mat, flags = bsp.face_material(f)
        if flags & SKIP_MASK:
            continue
        g = clean_material(mat)
        if f[6] >= 0:
            groups[g].extend(bsp.displacement_tris(f))
        else:
            p = bsp.face_points(f)
            for k in range(1, len(p) - 1):
                groups[g].append((p[0], p[k], p[k + 1]))

    index, verts, body = {}, [], []

    def idx(p):
        q = to_godot(p)
        q = (round(q[0], 4), round(q[1], 4), round(q[2], 4))
        if q not in index:
            index[q] = len(verts) + 1
            verts.append(q)
        return index[q]

    for g in sorted(groups):
        name = g.replace("/", "_")
        body.append("g %s\nusemtl %s" % (name, name))
        for t in groups[g]:
            a, b, c = idx(t[0]), idx(t[1]), idx(t[2])
            if a == b or b == c or a == c:
                continue          # degenerate after rounding; Godot drops these anyway
            body.append("f %d %d %d" % (a, b, c))
    with open(out_path, "w") as fh:
        fh.write("# %s -- world geometry in GENRE UNITS, Godot axes\n" % os.path.basename(bsp.path))
        fh.write("# multiply by G2GUnits.METRES_PER_UNIT for metres\n")
        for v in verts:
            fh.write("v %.4f %.4f %.4f\n" % v)
        fh.write("\n".join(body) + "\n")
    return len(verts), sum(len(v) for v in groups.values()), sorted(groups)


# Entities worth carrying across. Everything else in one of these maps is round logic,
# weapons and decoration this game has no use for.
WANTED = {
    "info_player_terrorist", "info_player_counterterrorist", "info_player_start",
    "info_teleport_destination", "trigger_teleport", "trigger_multiple",
    "trigger_once", "trigger_push", "trigger_hurt", "func_button", "worldspawn",
}


def write_entities(bsp, out_path):
    out = []
    for e in bsp.entities:
        cls = e.get("classname", "")
        if cls not in WANTED:
            continue
        rec = {k: v for k, v in e.items() if k != "hammerid"}
        if "origin" in e:
            try:
                p = [float(x) for x in e["origin"].split()]
                rec["origin_godot"] = list(to_godot(p))
            except ValueError:
                pass
        model = e.get("model", "")
        if model.startswith("*"):
            mi = int(model[1:])
            if mi < len(bsp.models):
                mins, maxs = bsp.model_bounds(mi)
                a, b = to_godot(mins), to_godot(maxs)
                rec["aabb_min_godot"] = [min(a[i], b[i]) for i in range(3)]
                rec["aabb_max_godot"] = [max(a[i], b[i]) for i in range(3)]
        out.append(rec)
    with open(out_path, "w") as fh:
        json.dump({"source": os.path.basename(bsp.path), "units": "genre units, Godot axes",
                   "entities": out}, fh, indent=1)
    return len(out)


def main(argv):
    if len(argv) < 3:
        print(__doc__.strip().splitlines()[2].strip())
        print("usage: bsp_read.py <map.bsp> <out-dir>")
        return 2
    src, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0].lower()
    bsp = Bsp(src).load()
    mins, maxs = bsp.model_bounds(0)
    obj = os.path.join(out_dir, stem + ".obj")
    ents = os.path.join(out_dir, stem + "_entities.json")
    nv, nt, mats = write_obj(bsp, obj)
    ne = write_entities(bsp, ents)
    print("%s  VBSP v%d" % (os.path.basename(src), bsp.version))
    print("  world  %.0f x %.0f x %.0f units" % tuple(maxs[i] - mins[i] for i in range(3)))
    print("  %s  %d verts, %d tris, %d materials" % (obj, nv, nt, len(mats)))
    print("  %s  %d entities" % (ents, ne))
    print("  materials: %s" % ", ".join(mats[:8]) + (" ..." if len(mats) > 8 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
