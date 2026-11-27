# printshop

Code to printable parts. Everything is built as exact solids with
[manifold3d](https://github.com/elalish/manifold), so every output is watertight and slicer-ready, and every
fit is a number in a printer profile rather than a guess baked into a model.

```bash
pip install -e .[dev]
printshop card examples/            # tolerance card: five 2x2 plates sweeping stud/tube fit (1-5 dimples)
printshop joints examples/          # print-in-place hinge + captured ball joint test pieces
printshop brick 2x4 brick.stl       # a 2x4 brick (--plates 1 for a plate)
pytest
```

## Burritos

Chaotic Attack burritos print as multi-colour figures on a stud-grid base that clicks onto a plate.
Two steps: dump the game's three.js models, then build solids from the dump.

```bash
(cd ../chaotic-attack && npm install)          # once, so `three` resolves
(cd tools && npm install)                      # once: tsx
tools/node_modules/.bin/tsx tools/dump_burrito.mts ../chaotic-attack --all --out burritos/   # or name kinds: yuri madison
printshop burrito burritos/*.json prints/      # --height 40 (mm, figure only) --colors 4 --no-base
```

Each burrito gets a 3MF (one object per colour plus the base, colours already assigned), an STL and a
PNG preview, and prints notes on what it changed to make the model printable:

- **Open surfaces** (capes, half-torus smiles, hoods) become shells `min_wall` thick; closed parts
  thinner than that (an extruded bolt) are stretched to `min_wall` along their thin direction.
- **Floating parts** (a staff held beside a hand, eyes that hover a hair off the wrap) get a short
  strut in their own colour; specks too small to print are dropped.
- **Overlaps** are resolved smallest-part-wins, so eyes and pins cut into the wrap.
- **Colours** merge (closest in L\*a\*b\*, smaller into larger) down to `--colors`, 4 for an AMS. The
  base shares the figure's darkest filament, so it costs no extra slot.
- **Textured wraps** (rainbow, sweater, leopard, swirl) print in the texture's dominant colour: the
  dump has no real canvas, so a stand-in counts how much area each fill colour paints.

All 21 burritos export (about 1–3 s each at 40 mm). Thin details such as sprinkles and heart pins
are at the edge of a 0.4 mm nozzle at that size; `--height 60` helps.
```

Each command writes an STL (all parts), a 3MF (separate named, coloured objects for multi-colour printers)
and a shaded PNG preview.

## What's here

| Module | What it does |
|---|---|
| `profiles.py` | The numbers that decide fit: stud/tube sizes, wall, joint clearance, XY compensation. `fdm-0.4` and `resin` starting points. |
| `bricks.py` | Bricks and plates on the common 8 mm stud grid; tolerance card. |
| `joints.py` | Print-in-place hinge and captured ball-and-socket (with a cone limit). |
| `checks.py` | One piece? Stands up (centre of mass inside the footprint, with margin)? Size, volume. |
| `burrito.py` | Chaotic Attack burritos from a model dump: thicken, strut, resolve overlaps, merge colours, seat on a base. |
| `export.py` | Binary STL and multi-object, multi-colour 3MF. |
| `preview.py` | Software-rendered PNG previews (no GPU or Blender needed). |

Tests check that bricks are one solid at nominal size, that joint parts are separate with exactly the
profile's clearance, and that a hinge leaf or a ball cannot be pulled out.

## Calibrating a printer

1. Print `printshop card` and `printshop joints` with the starting profile.
2. Press each card plate onto a real plate, and a real 2x2 onto it. Count the dimples on the one that clicks
   and holds without splitting; that sets `stud_delta` / `tube_delta` for the profile.
3. Work the joint pieces free. If they are fused, raise `joint_clearance`; if sloppy, lower it.
4. Save the result as a named profile in `profiles.py`. Everything else picks it up.

## Roadmap

1. **Calibrate** on the first printer (above).
2. ~~**Burritos.**~~ Done: `tools/dump_burrito.mts` + `printshop burrito` (above). Next: print one, check
   the base's clutch and the thinnest details, and tune the defaults.
3. **Brick-system figures and accessories.** Hands that grip the 3.2 mm bar, accessories built on that bar,
   heads on studs, hip pins.
4. **Articulated rabbitstew champions.** Bodies come from `build_model()`; each joint becomes a printed joint
   at its MuJoCo anchor and axis: hinge to a pin hinge with stops at the joint range, ball to a captured
   socket with a cone limit, weld to fused. MuJoCo can sweep each printed joint through its range to check
   that no parts collide. First case is RBT-19 P-801 holistic generation 590: three moving joints (two ball,
   one hinge at ±37°), thinnest jointed part 0.119 m. A 12 mm ball housing needs about 100 mm per model metre,
   so roughly a 12-13 cm figure. Its two ball joints are unlimited in the simulation, which a printed socket
   cannot be, so the print needs a cone limit the simulation never had.
5. **Stability in MuJoCo** for posed figures: drop the print onto a floor and see whether it stays up.

Brick compatibility is with the stud system only. Do not name or sell anything as LEGO.
