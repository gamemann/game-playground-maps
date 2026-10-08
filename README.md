# game-playground-maps

Custom sandbox maps for [game-playground](../game-playground), as JSON documents: boxes, a spawn, and the places a player is not meant to reach.

- `maps/pgc_plots.json` — **Build Plots**: eight plots of eight grounds (ice and rubber among them) with claim pads round a spawn plaza, a depot of planks and crates, trampolines, a pond, and a viewing deck.
- `maps/pgc_quarry.json` — **Quarry**: a two-terrace pit with ramps, rails and a cart, a flooded sump with steps out, boulders on the rim, barrels to blow up, and a blasting hut with a lever on its door.
- `maps/pgc_slopes.json` — **Slide Hill**: a hill to a high deck with a pen to be thrown from, sleds waiting at the head of a snow slope with an ice run-out, a halfpipe, and a frozen pond with thin ice.
- `maps/pgc_town.json` — **Town**: two roads, five buildings with glass windows, doors on buttons and ramps to their roofs, a fountain plaza with a stage, stalls, hedges and a trampoline, and a car park with two buggies.
- `maps/pgc_islands.json` — **Sky Islands**: six floating islands climbing a ring on bridges over a lava lake, and an ice slide from the top one back to the first, with boulders waiting at its head.
- `maps/pgc_site.json` — **Construction Site**: a half-built frame climbed by switchback ramps, a tower crane, material piles, a flooded excavation, a sand heap, a rack of glass panes, a site office, and a kicker and bumps for the buggies.
- `maps/pgc_warehouse.json` — **Warehouse**: a warehouse at dock height with racking full of crates, a catwalk with barrels, high windows, a glazed office, a cold store with an ice floor, and a yard of containers.
- `maps/pgc_canyon.json` — **Canyon**: two mesas either side of a canyon with a river down it, shallow at the ends and deep in the middle, a road bridge, a balance beam, a broken bridge to jump in a buggy, and boulders to push in.
- `maps/pgc_harbour.json` — **Harbour**: piers over a basin of water with slipways out, boats to jump onto, quay cranes, a freighter, and a lighthouse with a glass lantern, climbed by a spiral to throw things off.
- `maps/pgc_bowl.json` — **Fling Bowl**: a 30-degree bowl with two ice chutes and a rim walkway, boulders and sleds to send down it, a rubber pedestal in the middle, and a diving board.
- `maps/pgc_obstacle.json` — **Obstacle Park**: steps, stepping stones, a beam over a splash pool and a climb to a gate on a button, then a spiral of ledges up a tower whose button opens a vault.
- `maps/pgc_nature.json` — **Nature**: a meadow with a snow field and an ice rink, a mud pit, a sand beach and a pond, a lava pit with a rock bridge, a frozen lake under thin ice with a diving board, a slime swamp, bushes to hide in, trampolines and a glass greenhouse.

The game picks these up through a link (`game-playground/maps/custom`, made by dot-bootstrap) or, delivered, as a pack the game names under `dependencies`. Edit `tools/build_maps.py` and run it to change a map; the format is described in game-playground's `maps/pg_data.gd`.

MIT licensed.
