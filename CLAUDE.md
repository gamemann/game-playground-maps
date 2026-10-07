# game-playground-maps

Custom sandbox maps for game-playground, as JSON documents. Read `../../CLAUDE.md` and `../game-playground/CLAUDE.md` first: the format is defined, validated and built by game-playground's `maps/pg_data.gd`.

**`maps/` is what the game reads**, through a dot-bootstrap link (`game-playground/.gitignore`: `# bootstrap-link: game-playground-maps/maps` → `/maps/custom`). `Playground.map_catalogue()` adds every `.json` there as a `DotMapDef` built by the shared `res://maps/pg_data.tscn`, with the document's path in `meta.doc`; a document that does not read is left out with a WARN, and an id the catalogue already has is never replaced.

**Why documents and not map scripts.** The built-in maps are `_build()` scripts. A map delivered in a pack of its own is mounted at another prefix than the game, and a script there that `extends` the game's map base by path names a path that is only right in one of the two places it runs (the family's mount constraint). Boxes are data: either pack can be anywhere.

**`tools/build_maps.py` writes every document, and the JSON is committed.** Edit the builder, run it, commit both; `--check` fails when a committed file differs. Ramps are placed by their top surface's two ends and dropped along their normal by half their thickness, so the surface meets the ground exactly at both ends (dropped vertically, the top end is a lip, and over a step's height a lip is a wall).

## The maps

- **`pgc_plots` — Build Plots.** A 160 m walled plate: a spawn plaza in the middle, eight 26 m plots on a 40 m pitch round it, each a 0.2 m pad (a step) in its own colour with a 2 m claim pad on the path in front of it, and a viewing deck 4 m up in the north-west corner on a 20-degree ramp. After the plot-and-claim-pad layout of the 2026-10-05 reference video (`/extra/external/video/26-10-05/playground01.mp4`); claiming is drawn, not implemented.
- **`pgc_quarry` — Quarry.** A pit in two terraces (rim at 0, terrace at -6, floor at -12) with 6 m ramps between each level on the north and south sides, offset so the way down is a walk round; rails across the pit floor and along the north terrace (0.15 m, a step), a cart on the pit rails (1.0 m, a climb), three climbable ore piles and two 2.5 m boulders nobody climbs. After the mine-cart area in the same video.

Both are surveyed by `game-playground`'s `headless_playground` (*the hand-built maps, surveyed*: no slot, nothing unreached but what the document declares, no trap) and load through the catalogue on a dedicated server (`dedicated`'s map commands: `map pgc_quarry`). `game-playground/tools/screenshot.sh pgc_plots` / `pgc_quarry` renders them.

## Delivering it (not done yet)

A client builds the map too, so this is a **`dependencies`** pack, not `server_dependencies`: every client fetches it in the same content sync as the game. Both ends then add `<mount prefix>/maps` — the server from the game manager's dependency keys (`PlaygroundModule._add_delivered_maps`), the client from `DotClientLink.content_extra` (`PlaygroundClient._ready`). To ship: a `content/playground_maps/pack.json` in dot-server-deploy (`tmc/playground_maps`, `exclude_dirs: ["tools"]`), `dependencies: [tmc/playground_maps@0.1.0]` in `content/playground/game.yml`, publish both, and a client shell with this game-playground. Christian's call; nothing is published.

**Not yet on GitHub** (2026-10-07): `dot-bootstrap/projects.tsv` names `gamemann/game-playground-maps`; the repository is the owner's to create.
