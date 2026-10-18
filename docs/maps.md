# The maps

What each map is for and the measurements its layout depends on. Every one has materials and props; dimensions that a jump, a slide or the survey depends on are kept, because changing them changes what is reachable.

The player's jump, which every gap and step here is sized against: 4.75 m level, 3.68 m up 0.8 m, 3.23 m up 1.0 m; a jump climbs 1.035 m. Walkable slopes are under 46 degrees.

## `pgc_plots`: Build Plots

A 160 m walled plate: a spawn plaza in the middle, eight 26 m plots on a 40 m pitch round it, each a 0.2 m pad (a step) with a 2 m claim pad on the path in front of it, and a viewing deck 4 m up in the north-west corner on a 20-degree ramp. Claiming is drawn, not implemented. The plots are eight grounds to build on (concrete, wood, sand, snow, ice, metal, dirt, rubber) on grass; the plaza is concrete with two trampolines and a supply depot of loose planks, panels, crates and a barrel. A pond in the south-east corner: a hole 18 m square in 3.5 m of ground, water 2.2 m deep over sand, steps across its west edge.

## `pgc_quarry`: Quarry

A pit in two terraces (rim at 0, terrace at -6, floor at -12) with 6 m ramps between each level on the north and south sides, offset so the way down is a walk round. Rails across the pit floor and the north terrace (0.15 m, a step), a cart on the pit rails (1.0 m, a climb), three climbable ore piles and two 2.5 m boulders nobody climbs; three more boulders on the north rim one push from the edge. A blasting hut on the west terrace whose door is wired to a lever outside. A flooded sump in the pit floor's south-east corner: 24 m square and 3 m deep against two terrace walls, water to 0.3 m under the floor over mud, steps across its west edge, the corner boulder standing on the bed so it breaks the surface at 2.5 m.

## `pgc_slopes`: Slide Hill

A 180 m walled plate. A 14-degree hill 80 m long up to a 30 x 20 m deck 20 m up, with a pen on it (a 1 m wall round 8 m, under what a jump climbs, so nobody is shut in) to stand in and be picked up and thrown from; a 24-degree snow slope down the far side, and an ice run-out to the wall. Four sleds (planks at friction 0.05) on the deck: one nudged at 4 m/s slides from the deck to the far wall.

**The slope angles are measured, not assumed**: at the catalogue's friction (1.0) a plank or crate settles on the slope and stays, so it can be built on; at friction 0.2 (the tool gun's properties) it slides about 35 m to the bottom, and prop surfing carries whoever stands on it. Grass and snow still hold a crate (0.8 and 0.5 against the 0.25 and 0.45 the slopes need). A 45-degree slope would slide everything at the default friction and nobody could walk it. On the east side a halfpipe: two 31-degree wood faces 14 m apart, each topped by a 5 m ledge 6 m up. A frozen pond on the west: water 2.4 m deep under thin ice level with the grass, in a snow bank, steps out under it.

## `pgc_town`: Town

A 200 m walled town on grass. Two crossing roads 14 m wide (the north-south one a hair higher, so the crossing is one surface), five buildings on 0.15 m pavements. Each building has a doorway with **a door prop wired to a button outside and one inside** (F on the door works too), loose crates inside, and a ramp up the side wall away from the road to a post level with the roof, touching the wall. Every wall but the one a roof ramp climbs has 1.6 m windows at 1.0-2.4 m (and 4.0-5.4 m on the 7 and 9 m buildings), with shop windows kept 3 m from each door. A fountain plaza (0.4 m of water: a paddle; a player swims from 1 m) with trees, a stage, market stalls, benches and a trampoline; a car park with two buggies.

## `pgc_islands`: Sky Islands

A 240 m walled plate. Six 20 m islands on a 55 m ring, tops 8 to 33 m, joined in order by 4 m sloped wooden bridges (`bridge()`, about 10 degrees, no rails), and a ramp from the ground to the first. From the top island a 6 m ice slide runs straight back down to the first, 25 m over 32 (about 38 degrees): a slide for a player too, so the bridges are the way up. A boulder nudged at 3 m/s at its head rolls down and rests on the first island. The floor inside the ring is a 76 m lava lake in a 0.8 m rock rim, so a fall off an inner corner or a bridge goes back to the spawn; a fall outside lands on grass that leads back to the ramp, so nowhere is a trap.

## `pgc_site`: Construction Site

A 180 m dirt plate inside a 3 m fence. A half-built concrete frame, 30 x 20 m, three open floors every 4.5 m on 0.6 m columns, climbed by a wooden switchback on its east side: lanes A and B, landings spanning both and touching each slab, the third ramp 9 m over the first, and the ramps starting flush with the frame. A tower crane (a 28 m mast and a 40 m jib, declared), a dirt kicker and a bumps track for two buggies, a site office with a button-wired door and glass on three sides, material piles to build with, a flooded excavation (20 x 14 m, 2.1 m of muddy water, steps up its north edge), and a glazing rack of four real panes 1.5 m apart.

## `pgc_warehouse`: Warehouse

The first indoor map. A 160 m yard holds an 80 x 50 m hall whose floor is at dock height, 1.2 m: a climb no jump makes. 12 m walls and a roof, two 8 m loading doorways: the east one has a ramp up from the yard; the west one is a sheer dock edge to drive a buggy off. Inside: four 30 m rows of racking with shelves at 2.5 and 5 m (declared) holding loose crates, and a 2.5 m catwalk 6 m up along the north and east walls, reached by a ramp up the north wall and **starting exactly where its ramp tops out**. Clerestory panes 8-10.5 m up the walls, 1.6 m over the catwalk so nobody climbs into one. An office with a button-wired door; a cold store with an ice floor and ice blocks 1.6 m from its wall. Shipping containers in the yard, some two high, tops declared.

## `pgc_canyon`: Canyon

Two 90 m rock mesas, 20 m high, either side of a 40 m canyon, inside 24 m walls (4 m over the mesas, so a thrown prop stays in). Each mesa is reached by a 60 m ramp flush against the canyon wall (18 degrees). Three crossings: a railed road bridge at z 0, a 1.2 m balance beam at z -60, and at z 60 a broken bridge whose west half rises 3 m to a lip 12 m short of the flat east half. **Measured with a buggy off the lip**: at 12 m/s it falls into the canyon; at 16, 20 and 25 m/s it lands (the buggy tops out near 24). A river runs down the canyon: a channel 10 m wide in 4 m of ground, 0.55 m deep (waded) at both ends and 2.85 m deep for 105 m in the middle under both bridges, so a buggy that misses the jump lands in it; steps the channel's width at each end.

## `pgc_harbour`: Harbour

A 200 m harbour: a quay 4 m over a sunken basin of water (a 3.4 m volume, its surface 0.6 m under the quay: swum in, floated on), two slipways out of it (4 m over 22, about 10 degrees) so whoever is thrown in walks back, three 50 m timber piers with T-heads on pilings (3.6 m of headroom, so the basin floor runs underneath), and a rock mole out to a lighthouse. Two small boats lie 1.5 m off a pier's pilings with their decks 1 m under it (a hop down and a jump back; the 1.5 m keeps it from being a slot). A metal freighter along the mole. The lighthouse is a 6 m core climbed by a square spiral: seven `bridge()` sides 3 m up over 6 (27 degrees) between 3 m corner landings, and at 21 m a gallery round three sides, 2.5 m over the lane below, with barrels to throw off; its lantern room is glass. One water volume (`_test_water`). Beach balls float on the basin.

## `pgc_bowl`: Fling Bowl

A 96 m bowl: a 28 m sand floor with a 1 m rubber pedestal in the middle (an octagon of two squares, a jump; rubber jumps 1.8 times as high), 30-degree concrete sides 15 m high, an 8 m rim walkway with a 1.5 m parapet, and a diving board 8 m out over the north slope.

**The sides are a frustum of a 24-sided pyramid, one `bridge()` per side, each as wide as its side at the rim**, so neighbours overlap toward the middle; where they do, the facet whose own axis is nearer is the higher, so the surface is exactly the facet and the seams meet with no lip and no gap. Each slab is thick enough that its underside is under the ground at the rim, so there is no hollow under the bowl. The facets are 2 m wider than natural, hidden under their neighbours, to clear the survey's AABB reading ([history](history.md#the-bowls-sixteen-slots-that-were-not-there)). Pushed inward at 3 m/s from the rim, boulders, balls and sleds reach the floor and none climbs the far side. Two ice chutes, east and west: 3.6 m lanes of ice 0.1 m thick laid *on* a facet, not facets made of ice.

## `pgc_obstacle`: Obstacle Park

A 160 m field with a course from a pad: four 1 m steps, six 2 m stepping stones 2.5 m apart zigzagging at 4 m, a 0.8 m balance beam 12 m long over a splash pool, a 6 m landing, five blocks each 0.8 m higher and 2 m apart, and an 8 m platform with a wall across it whose door is wired to a button on each side. Past the gate an 8 m tower 20 m tall is climbed by fifteen ledges spiralling round it, each 0.8 m up and 2.25 m on (a loop is 6.4 m, so every ledge has headroom), to a deck to be thrown from into a sand pit, with a button that opens a vault by the start. Nothing asks for more than 2.5 m. **Measured with a bot driven box to box** (`headless_playground`'s route driving, the gate opened by its button): it makes every jump first time. The course is concrete and wood, which have no drag, so those measurements hold. A fall lands in the field, which leads back to the start.

## `pgc_nature`: Nature

The first map made of materials. A 220 m grass meadow with a snow field and a 30 x 20 m ice rink, a mud pit, a sand beach, a stone-rimmed pond entered over a 3 m landing on the rim with a ramp each side, a rock-rimmed lava pit with a rock bridge (its ramps flush with the bridge), three rubber trampolines, a rock outcrop with a wooden lookout, and a glass greenhouse. A frozen lake (water 1.6 m deep under thin ice in a 2 m stone basin, bed declared) with a diving board on a 5 m wooden tower whose 3 m drop goes through the ice; a slime swamp (a toxic pool in a 0.8 m rim, six stepping stones); foliage bushes to hide in. The pond's barrels and balls float at their waterline.

## `pgc_construct_small`: a converted community map

Converted from a community BSP file by `tools/import_bsp.py` (credit and removal-on-request in the document's `attribution`; the author's textures replaced by this game's materials over Kenney's CC0 Prototype Textures). Brushes become boxes (exact, turned, prism, or one tilted box per ramp); the water brush becomes a water volume. A 30 x 46 m concrete basin 8.5 m deep holds 7.6 m of water, and a ramp added in its north end, because a player thrown in could otherwise never leave it. The tall outer walls and a rail are declared. The two flat-plane maps first asked for were not converted: a plane is not a map.
