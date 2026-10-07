# game-playground-maps

Custom sandbox maps for game-playground, as JSON documents. Read `../../CLAUDE.md` and `../game-playground/CLAUDE.md` first: the format is defined, validated and built by game-playground's `maps/pg_data.gd`.

**`maps/` is what the game reads**, through a dot-bootstrap link (`game-playground/.gitignore`: `# bootstrap-link: game-playground-maps/maps` → `/maps/custom`). `Playground.map_catalogue()` adds every `.json` there as a `DotMapDef` built by the shared `res://maps/pg_data.tscn`, with the document's path in `meta.doc`; a document that does not read is left out with a WARN, and an id the catalogue already has is never replaced.

**Why documents and not map scripts.** The built-in maps are `_build()` scripts. A map delivered in a pack of its own is mounted at another prefix than the game, and a script there that `extends` the game's map base by path names a path that is only right in one of the two places it runs (the family's mount constraint). Boxes are data: either pack can be anywhere.

**Props.** A document may list `props` (catalogue ids, frozen unless `loose`) and `wires` between them, which game-playground puts down on the server when the map loads (its CLAUDE.md, *A map document can carry props*). `prop()` takes the floor a prop stands on and adds half its height from `HALF_HEIGHT`; keep that table in step with game-playground's catalogue.

**`tools/build_maps.py` writes every document, and the JSON is committed.** Edit the builder, run it, commit both; `--check` fails when a committed file differs. Ramps are placed by their top surface's two ends and dropped along their normal by half their thickness, so the surface meets the ground exactly at both ends (dropped vertically, the top end is a lip, and over a step's height a lip is a wall).

## The maps

- **`pgc_plots` — Build Plots.** A 160 m walled plate: a spawn plaza in the middle, eight 26 m plots on a 40 m pitch round it, each a 0.2 m pad (a step) in its own colour with a 2 m claim pad on the path in front of it, and a viewing deck 4 m up in the north-west corner on a 20-degree ramp. After the plot-and-claim-pad layout of the 2026-10-05 reference video (`/extra/external/video/26-10-05/playground01.mp4`); claiming is drawn, not implemented.
- **`pgc_quarry` — Quarry.** A pit in two terraces (rim at 0, terrace at -6, floor at -12) with 6 m ramps between each level on the north and south sides, offset so the way down is a walk round; rails across the pit floor and along the north terrace (0.15 m, a step), a cart on the pit rails (1.0 m, a climb), three climbable ore piles and two 2.5 m boulders nobody climbs. After the mine-cart area in the same video.

- **`pgc_slopes` — Slide Hill.** A 180 m walled plate. A 14-degree hill 80 m long up to a 30 x 20 m deck 20 m up, with a pen on it (a 1 m wall round 8 m, under the 1.035 m a jump climbs, so nobody is shut in) to stand in and be picked up and thrown from, after the same video's "stand in the box" loop; and a 24-degree slope down the far side. **Measured, not assumed**: at the catalogue's friction (1.0) a plank or crate settles on the slope and stays (0.6-0.9 m, the drop onto it), so it can be built on; with friction 0.2, set by the tool gun's Edit properties or Physical properties, it slides about 35 m to the bottom in six seconds, and game-playground's prop surfing carries whoever stands on it. A 45-degree slope would slide everything at the default friction and nobody could walk it. On the east side a halfpipe: two 31-degree faces 14 m apart, each topped by a 5 m ledge 6 m up. `ramp_x` is `ramp_z`'s twin for ramps rising along X.

- **`pgc_town` — Town.** A 200 m walled town on grass. Two crossing roads 14 m wide (the north-south one a hair higher, so the crossing is one surface), five buildings on 0.15 m pavements. Each building has a doorway with a **door prop wired to a button outside and one inside** (F on the door works too), loose crates and a barrel inside, and a ramp up the side wall away from the road to a post level with the roof. The post touches the wall: the first version left 0.2 m between them, a slot. A fountain plaza has trees round it, a stage, three market stalls with goods, benches and beach balls. Street trees and lamps run down the north-south road, and a car park in the south-east corner holds two buggies. The first map to use the document's `props` and `wires`.

All of them are surveyed by `game-playground`'s `headless_playground` (*the hand-built maps, surveyed*: no slot, nothing unreached but what the document declares, no trap) and load through the catalogue on a dedicated server (`dedicated`'s map commands: `map pgc_quarry`). `game-playground/tools/screenshot.sh pgc_plots` / `pgc_quarry` renders them.

## Delivering it (not done yet)

A client builds the map too, so this is a **`dependencies`** pack, not `server_dependencies`: every client fetches it in the same content sync as the game. Both ends then add `<mount prefix>/maps` — the server from the game manager's dependency keys (`PlaygroundModule._add_delivered_maps`), the client from `DotClientLink.content_extra` (`PlaygroundClient._ready`). To ship: a `content/playground_maps/pack.json` in dot-server-deploy (`tmc/playground_maps`, `exclude_dirs: ["tools"]`), `dependencies: [tmc/playground_maps@0.1.0]` in `content/playground/game.yml`, publish both, and a client shell with this game-playground. Christian's call; nothing is published.

**Not yet on GitHub** (2026-10-07): `dot-bootstrap/projects.tsv` names `gamemann/game-playground-maps`; the repository is the owner's to create.
