# History

What building these maps found, in the shapes worth recognising again. Most were found by game-playground's survey (`headless_playground`), its `tools/map_props.gd`, or a render.

## Slots the survey found

A slot is a gap a player can fall into and not climb out of. Each of these was a measured distance that looked harmless in the builder:

- **Town**: a roof ramp's post stood 0.2 m from the wall. It touches the wall now.
- **Construction Site**: ramps starting 1 m in from the frame left a 0.4 m slot against the corner column. They start flush.
- **Warehouse**: the catwalk overlapped its ramp's end, leaving 1.4 m of headroom where they met, and the survey reported the whole catwalk unreached. It starts exactly where the ramp tops out. An ice block drawn 0.6 m from the cold store's wall was moved to 1.6 m.
- **Nature**: two ramps meeting the pond's rim straight left a 0.7 m slot (now a 3 m landing between them); the lava bridge's ramps 0.25 m short were a slot.
- **Obstacle Park**: the beam's second post stood 0.3 m from a step's face; it moved from z 10 to z 8.
- **Harbour** passed on the first run, and its small boats sit 1.5 m off the pilings precisely so the gap is not a slot.

## The bowl's sixteen slots that were not there

The survey reads a tilted box as its world AABB, and at the natural width the AABBs of two facets some way apart, or a facet and a rim block, came 0.06 to 0.65 m apart. The surface had no gap. Every pair cleared from 1.2 m wider; the facets are 2 m wider, hidden under their neighbours either way. When the survey reports a slot between tilted boxes, check the geometry before believing it, and widen rather than weaken the check.

## Props launched by buoyancy

Loose props put down on a water bed were thrown out by game-playground's buoyancy: a beach ball on the harbour's bed went two kilometres up, and Nature's pond barrels and balls 60 and 940 m. `tools/map_props.gd` reported it on the committed maps. Props in water are placed at their own waterline.

## What the route measurements found

**Obstacle Park's first landing was 4 m**, and the bot missed the first block every time on its first try, at 2 m and 1.5 m spacing alike, because turning off the beam left it 2 m to get up to speed. The landing is 6 m and the course 2.5 m further west. A gap that fits the jump on paper can still be missed for want of a run-up.

## What the render found

- Slide Hill's hill vanished into the plate in grass's own look; it is a lighter green, and a snow bank was added so the ice was not a pale square on the lawn.
- Fling Bowl's crates disappeared on an orange pedestal and the floor disappeared against the white facets; the pedestal is red and the floor sand. Its ice chutes were first two facets made of ice, and the overlapping slabs inside them showed through; they are thin ice lanes laid on a facet.
- Harbour's gallery barrels were on the side the camera stands on and were moved.
