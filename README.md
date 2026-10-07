# game-playground-maps

Custom sandbox maps for [game-playground](../game-playground), as JSON documents: boxes, a spawn, and the places a player is not meant to reach.

- `maps/pgc_plots.json` — **Build Plots**: eight plots with claim pads round a spawn plaza, and a viewing deck.
- `maps/pgc_quarry.json` — **Quarry**: a two-terrace pit with ramps, rails, a cart and boulders.
- `maps/pgc_slopes.json` — **Slide Hill**: a hill to a high deck with a pen to be thrown from, a far slope that props slide down once their friction is turned down, and a halfpipe.

The game picks these up through a link (`game-playground/maps/custom`, made by dot-bootstrap) or, delivered, as a pack the game names under `dependencies`. Edit `tools/build_maps.py` and run it to change a map; the format is described in game-playground's `maps/pg_data.gd`.

MIT licensed.
