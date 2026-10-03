# printshop

Code to printable parts. Everything is built as exact solids with
[manifold3d](https://github.com/elalish/manifold), so every output is watertight and slicer-ready, and every
fit is a number in a printer profile rather than a guess baked into a model.

```bash
pip install -e .[dev]
printshop card examples/            # tolerance card: five 2x2 plates sweeping stud/tube fit (1-5 dimples)
printshop joints examples/          # print-in-place hinge + captured ball joint test pieces
printshop brick 2x4 brick.stl       # a 2x4 brick (--plates 1 for a plate)
pip install -e .[rabbitstew]        # optional: rabbitstew (from git) + MuJoCo 3.14.0
printshop champion RBT-19-P-801 holistic 590 examples/   # a champion posed on a plinth
python -m pytest
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
| `sources/rabbitstew.py` | Rabbitstew champions: re-simulate a solo bout, take the pose, every unit a solid, fused onto a plinth. |

Tests check that bricks are one solid at nominal size, that joint parts are separate with exactly the
profile's clearance, and that a hinge leaf or a ball cannot be pulled out.

## Rabbitstew champions

`printshop champion RUN KIND GEN OUT_DIR` re-simulates the champion's solo bout exactly as rabbitstew's
`scripts/shots.py` does (the run's config, opponent proxy on, spawn from `--seed`, default 3), takes its pose
at `--time` (default mid-bout), and builds every box, sphere and cylinder as a solid at that pose. Units are
grown by half the minimum wall so touching parts fuse; anything still floating is bridged by a strut. The
figure is scaled to `--length` mm across and its feet sink into a `--plinth` mm round base. Alongside the
STL / 3MF / PNG it writes a `.json` with the provenance (run, generation, seed, frame, MuJoCo version,
scale) and the checks.

RUN is a rabbitstew run directory or a bundled run (`printshop/data/rabbitstew/`, currently `RBT-19-P-801`).
This is a port of rabbitstew's `scripts/print_champion.py` (on its branch `ccr-0870ebac-5zhnoi`, not yet on
main), and with `--min-wall 1.6` it reproduces that script's print to the 0.01 mm: frame 188 at 7.52 s,
85.84 mm per model metre, 108 x 108 x 52 mm. `examples/champion-rbt-19-p-801-holistic-g590.*` is that print.

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
