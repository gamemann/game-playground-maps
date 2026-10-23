# game-playground-maps

Custom sandbox maps for game-playground, as JSON documents written by `tools/build_maps.py`. The format is defined, validated and built by game-playground's `maps/pg_data.gd`; this repository only holds the documents and the builder.

Read the family [CLAUDE.md](../../CLAUDE.md) and game-playground's [CLAUDE.md](../game-playground/CLAUDE.md) first, and its [maps.md](../game-playground/docs/maps.md) for the format, materials and the survey.

## Read before

| Read | Before |
| --- | --- |
| [docs/building.md](docs/building.md) | changing the builder or any map: why documents, how the game reads them, the helpers, materials, props, checking, delivery |
| [docs/maps.md](docs/maps.md) | changing one map: what it is for and the measurements its layout depends on |
| [docs/history.md](docs/history.md) | what the survey, the prop probe and the renders found |

## Layout

| Path | What |
| --- | --- |
| `maps/*.json` | the fourteen documents (`pgc_*`), committed (twelve built by `build_maps.py`, two converted by `import_bsp.py`, which `--check` does not rewrite); linked into game-playground as `maps/custom` by dot-bootstrap |
| `tools/build_maps.py` | writes every document; `--check` fails when a committed file differs |
| `tools/import_bsp.py`, `tools/bsp_read.py` | converts a community BSP to a document: brushes to boxes by dot-map's `boxes.decompose(tilt=True)` (never a local copy; this file is only the adapter: document format, `GAME_MATERIAL`, configs), a brush's surface from dot-map's shared `tools/bsp/dotbsp/source_textures.tsv` (a new texture goes there, never here; `bsp.py unmapped <bsp>` lists what it misses), turned into this game's materials by `GAME_MATERIAL`; the config table holds each map's credit, region and any `overrides` the list cannot say |
| `.github/workflows/` | `check.yml` (the builder's `--check`), `release.yml` (the pack, from a `v*` tag) |

## Running and testing

- Edit `tools/build_maps.py`, run `python3 tools/build_maps.py`, commit the builder and the JSON together. `python3 tools/build_maps.py --check` must pass.
- Then, in game-playground: `headless_playground` surveys every map (slots, reachability, traps), `tools/map_props.gd` loads every map and checks props stay put, and `tools/screenshot.sh <map>` renders one. A map change is not done until all three pass and the picture has been looked at. [building](docs/building.md#checking-a-map)

## Rules that bite

- Maps are documents, never scripts: a script in a mounted pack names a path that is wrong in one of the two places it runs. [building](docs/building.md#why-documents-and-not-map-scripts)
- Place ramps by their top surface's two ends; never drop one vertically. [building](docs/building.md#the-builder)
- Size every gap and step against the jump (4.75 m level, 1.035 m climb) and leave a run-up; no gap a player can fall into and not leave. [maps](docs/maps.md), [history](docs/history.md#slots-the-survey-found)
- A ramp meets what it climbs to flush, or overlaps it, never 0.2-1 m short; a post touches its wall. [history](docs/history.md#slots-the-survey-found)
- Glass fills its opening the wall's whole thickness; windows stay 3 m from a doorway's buttons. [building](docs/building.md#the-builder)
- Never give a slow material (grass, dirt, sand, snow) to anything a jump was measured on. [building](docs/building.md#materials)
- Never put a loose prop under water; place it at its waterline. [building](docs/building.md#props-and-wires)
- Toys are hints in `TOYS` that `settle` moves onto clear floor; a hint that settles nowhere is an error, never a toy left out (a switch names lamps by index). [building](docs/building.md#toys)
- Keep `HALF_HEIGHT` in step with game-playground's prop catalogue. [building](docs/building.md#props-and-wires)
- Declare what is meant to be unreached (crane jibs, shelves, container tops, lake beds) rather than let the survey fail on it. [building](docs/building.md#checking-a-map)
- A survey slot between tilted boxes may be the AABB reading; check before believing it. [history](docs/history.md#the-bowls-sixteen-slots-that-were-not-there)
- The pack is a `dependencies` pack, not `server_dependencies`: the client builds the map too. [building](docs/building.md#delivery)
- `project.godot` exists only so dot-ci's release can import this repository and attach the `-pack.zip`; it carries the editor's own header and no comments, because the editor rewrites the file on its first save and a checkout would show it modified.

**`provides.json` is what lists this pack in the Workshop, and `tools/build_provides.py` writes it** from the documents in the folder (an entry per map, `map_kind` and the game it is for are constants at the top). Edit the script, run it, commit both; `--check` (CI) fails on a stale file. A pack whose newest READY version has no `provides` block is not a Workshop item. It ships because the pack takes every file outside the excluded folders.
