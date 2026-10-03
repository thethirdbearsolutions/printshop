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

Each command writes an STL (all parts), a 3MF (separate named, coloured objects for multi-colour printers)
and a shaded PNG preview.

## What's here

| Module | What it does |
|---|---|
| `profiles.py` | The numbers that decide fit: stud/tube sizes, wall, joint clearance, XY compensation. `fdm-0.4` and `resin` starting points. |
| `bricks.py` | Bricks and plates on the common 8 mm stud grid; tolerance card. |
| `joints.py` | Print-in-place hinge and captured ball-and-socket (with a cone limit). |
| `checks.py` | One piece? Stands up (centre of mass inside the footprint, with margin)? Size, volume. |
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
2. **Burritos.** Export Chaotic Attack characters from `buildBurrito()` (three.js primitives) as parts and
   colours, thicken zero-thickness planes, fuse, and give them a socket base that fits the stud grid, so they
   stand on a plate. Multi-colour 3MF.
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
