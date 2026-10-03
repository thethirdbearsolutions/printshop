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
printshop jointed RBT-19-P-801 holistic 590 examples/    # the champion with printed joints, print-in-place
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
| `mechanisms.py` | Joints at any anchor and axis: captured ball socket (cone limit), pin hinge (stop slot), captive T rail. |
| `articulate.py` | Bodies + joints to separate printable pieces, carved so every joint moves through its range. |
| `motion.py` | Checks for articulated figures: one piece each, gaps, capture, sweeps; posing. |
| `orient.py` | Which way up to print: least support for the most bed contact; flat feet. |
| `sources/rabbitstew_jointed.py` | Rabbitstew champions with every MuJoCo joint as a printed joint. |
| `sources/rabbitstew.py` | Rabbitstew champions: re-simulate a solo bout, take the pose, every unit a solid, fused onto a plinth. |

Tests check that bricks are one solid at nominal size, that joint parts are separate with exactly the
profile's clearance, and that a hinge leaf or a ball cannot be pulled out; for articulated figures, that
every body is one separate piece, every gap is at least the clearance, every joint is captured, and sweeping
each joint through its range never collides.

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

## Jointed champions

`printshop jointed RUN KIND GEN OUT_DIR` builds the champion from rabbitstew's `build_model()` at rest (every
joint at zero) with no plinth. Parts welded together (rabbitstew's FIXED links) become one body, with a
strut between their centres. Each moving joint's anchor, axis, type and range come from MuJoCo and become:

| MuJoCo | Printed |
|---|---|
| hinge | pin hinge: end knuckles and pin on the parent, a bored middle knuckle on a web on the child; a ring round the middle knuckle has a slot the web stops against at the joint range |
| ball | captured socket on the parent, ball and neck on the child; the socket opening is the cone limit, as wide as the ball stays captured (at most 30°) |
| slide | captive T rail; the channel's ends stop it at the range (±5 mm if unlimited) |
| weld | fused |

Mechanisms are centred on the anchors, so they sit where the simulated parts meet. Each is sized to fit the
part it sits on (housing no thicker than that part) and how deep the child runs along the joint (where the neck
or web must land). The scale starts where a 12 mm ball housing is as thick as the thinnest part a joint touches
and grows 6% at a time until every joint fits.

Then every body is carved so it moves through its whole range without touching anything, with the profile's
`joint_clearance`. Bulk always gives way to mechanisms; where bulk meets bulk, the part that stays gives way to the
part that moves. Swept volumes are hulls of each primitive at neighbouring poses, so they are continuous, and a
ball joint's free twist is included (rabbitstew's limbs are round about their joint axis, so that costs nothing).

Last, the figure is turned to the orientation needing the least support for the most bed contact, and trimmed
1 mm flat underneath.

**RBT-19 P-801 holistic generation 590** (`examples/jointed-rbt-19-p-801-holistic-g590*`, `-posed.png` has every
joint at the end of its range). It is 113.65 mm per model metre, a 128 x 64 x 74 mm print. Four pieces, three
joints:

| Joint | MuJoCo | Printed |
|---|---|---|
| `r0_j1` trunk to big sphere | ball, unlimited | 4.5 mm ball, 12.9 mm housing, 26.5° cone |
| `r0_j3` trunk to sphere pair | hinge, ±36.6° | 2 mm pin, 10.2 mm housing, 15 mm long, stops at ±36.6° |
| `r0_j4` trunk to disc | ball, unlimited | 2.5 mm ball, 8.9 mm housing, 12.8° cone |

The scale is 113.65, not about 100, because of the disc: it is 0.053 m thick, and a 2.5 mm ball (the smallest worth
printing) needs 6 mm of it. Every gap is at least 0.35 mm, every joint is captured, and no sweep through the
range collides. It prints on the trunk's 45 x 12 mm top face, upside down, with 2,250 mm² of support (mostly
under the big sphere).

**Where the simulated body is not physically honest.** MuJoCo ignores contacts between a body and its parent,
and every child here overlaps the trunk even at rest (0.54-0.57 cm³ each). Swept through their ranges, the
uncarved shapes would overlap the trunk by 2.8 cm³ (big sphere), 1.8 cm³ (sphere pair) and 0.6 cm³ (disc).
The carving removed that: the trunk keeps 88% of its volume, the big sphere 99%, the sphere pair 96% and the
disc 86%. The `.json` beside the example has all of it (`checks.honesty`).

## Calibrating a printer

1. Print `printshop card` and `printshop joints` with the starting profile.
2. Press each card plate onto a real plate, and a real 2x2 onto it. Count the dimples on the one that clicks
   and holds without splitting; that sets `stud_delta` / `tube_delta` for the profile.
3. Work the joint pieces free. If they are fused, raise `joint_clearance`; if sloppy, lower it.
4. Save the result as a named profile in `profiles.py`. Everything else picks it up.

## Roadmap

1. ~~Rabbitstew champions as figurines~~ (`printshop champion`).
2. ~~Jointed rabbitstew champions~~ (`printshop jointed`).
3. **Burritos.** Export Chaotic Attack characters from `buildBurrito()` (three.js primitives) as parts and
   colours, thicken zero-thickness planes, fuse, and give them a socket base that fits the stud grid, so they
   stand on a plate. Multi-colour 3MF.
4. **Brick-system figures and accessories.** Hands that grip the 3.2 mm bar, accessories built on that bar,
   heads on studs, hip pins.
5. **Stability in MuJoCo** for posed figures: drop the print onto a floor and see whether it stays up.
6. **Calibrate** on the first printer (above), then print the jointed champion.

Brick compatibility is with the stud system only. Do not name or sell anything as LEGO.
