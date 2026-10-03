"""printshop command line.

    printshop card OUT_DIR [--profile fdm-0.4]          tolerance card: 2x2 plates sweeping stud/tube fit
    printshop brick WxL OUT.stl [--plates 3]             one brick (3 plates) or plate (1)
    printshop joints OUT_DIR [--profile fdm-0.4]         print-in-place hinge and ball joint test pieces
    printshop champion RUN KIND GEN OUT_DIR [--seed 3]   a rabbitstew champion posed on a plinth (needs the extra)
    printshop jointed RUN KIND GEN OUT_DIR [--mm M]      the champion with printed joints, laid out to print in place
    printshop burrito KIND OUT_DIR [--slots 4]           a Chaotic Attack burrito on a stud-grid base, in colour
    printshop figure OUT_DIR [--profile fdm-0.4]         a brick-system figure and its bar accessories
    printshop drop FILE.stl [--trials 8 --height 20]     does it stay up? a MuJoCo drop test (needs mujoco)
    printshop stand RUN KIND GEN OUT_DIR                 which pose of a jointed champion stands up?
"""
from __future__ import annotations

import argparse
import json
import os

from .bricks import brick, tolerance_card
from .checks import check
from .export import write_3mf, write_stl
from .joints import ball_joint, hinge
from .preview import PALETTE, render
from .profiles import PROFILES


def _emit(objects, stem: str) -> None:
    """objects: list of (name, Manifold). Writes STL (all), 3MF (separate objects) and a PNG preview."""
    write_stl([m for _, m in objects], stem + ".stl")
    write_3mf([(n, m, PALETTE[i % len(PALETTE)]) for i, (n, m) in enumerate(objects)], stem + ".3mf")
    render([(m, PALETTE[i % len(PALETTE)]) for i, (_, m) in enumerate(objects)], stem + ".png")
    print(f"wrote {stem}.stl / .3mf / .png")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="printshop", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("card"); c.add_argument("out"); c.add_argument("--profile", default="fdm-0.4")
    b = sub.add_parser("brick"); b.add_argument("size"); b.add_argument("out"); b.add_argument("--plates", type=int, default=3)
    b.add_argument("--profile", default="fdm-0.4")
    j = sub.add_parser("joints"); j.add_argument("out"); j.add_argument("--profile", default="fdm-0.4")
    ch = sub.add_parser("champion")
    for arg in ("run", "kind"):
        ch.add_argument(arg)
    ch.add_argument("gen", type=int); ch.add_argument("out"); ch.add_argument("--profile", default="fdm-0.4")
    ch.add_argument("--seed", type=int, default=3); ch.add_argument("--time", type=float, default=None)
    ch.add_argument("--length", type=float, default=90.0); ch.add_argument("--min-wall", type=float, default=None)
    ch.add_argument("--plinth", type=float, default=4.0)
    jt = sub.add_parser("jointed")
    for arg in ("run", "kind"):
        jt.add_argument(arg)
    jt.add_argument("gen", type=int); jt.add_argument("out"); jt.add_argument("--profile", default="fdm-0.4")
    jt.add_argument("--mm", type=float, default=None, help="mm per model metre (default: smallest that fits)")
    fg = sub.add_parser("figure"); fg.add_argument("out"); fg.add_argument("--profile", default="fdm-0.4")
    dr = sub.add_parser("drop"); dr.add_argument("stl"); dr.add_argument("--trials", type=int, default=8)
    dr.add_argument("--height", type=float, default=20.0, help="mm above the floor")
    dr.add_argument("--tilt", type=float, default=5.0, help="degrees of lean, in a random direction each trial")
    dr.add_argument("--shove", type=float, default=0.0, help="m/s sideways, the way it leans")
    dr.add_argument("--settle", action="store_true", help="first let it fall into the pose it rests in")
    st = sub.add_parser("stand")
    for arg in ("run", "kind"):
        st.add_argument(arg)
    st.add_argument("gen", type=int); st.add_argument("out"); st.add_argument("--profile", default="fdm-0.4")
    bu = sub.add_parser("burrito")
    bu.add_argument("kind", help="a bundled kind (madison, yuri, sebastian, firework) or an exporter .json.gz")
    bu.add_argument("out"); bu.add_argument("--profile", default="fdm-0.4")
    bu.add_argument("--slots", type=int, default=4, help="filament colours the printer holds")
    bu.add_argument("--mm", type=float, default=22.0, help="mm per three.js unit")
    bu.add_argument("--no-hero", action="store_true", help="without the earned costume")
    a = ap.parse_args(argv)
    profile = PROFILES[getattr(a, "profile", "fdm-0.4")]

    if a.cmd == "card":
        os.makedirs(a.out, exist_ok=True)
        _emit(tolerance_card(profile), os.path.join(a.out, f"tolerance-card-{profile.name}"))
    elif a.cmd == "brick":
        w, l = (int(x) for x in a.size.lower().split("x"))
        m = brick(w, l, a.plates, profile)
        write_stl(m, a.out)
        print(json.dumps(check(m).__dict__))
    elif a.cmd == "joints":
        os.makedirs(a.out, exist_ok=True)
        h_a, h_b = hinge(profile=profile)
        s, ball = ball_joint(profile=profile)
        _emit([("hinge-a", h_a), ("hinge-b", h_b), ("socket", s.translate([30, 0, 0])), ("ball", ball.translate([30, 0, 0]))],
              os.path.join(a.out, f"joint-gauge-{profile.name}"))
    elif a.cmd == "champion":
        from .sources import rabbitstew

        os.makedirs(a.out, exist_ok=True)
        champ = rabbitstew.load(a.run, a.kind, a.gen)
        body, info = rabbitstew.figurine(champ, a.seed, a.time, a.length, profile, a.min_wall, a.plinth)
        stem = os.path.join(a.out, f"champion-{champ.name}")
        _emit([(champ.name, body)], stem)
        _provenance(stem, info, body)
    elif a.cmd == "jointed":
        _jointed(a, profile)
    elif a.cmd == "drop":
        from .export import read_stl
        from .stability import drop_test, settle

        m = read_stl(a.stl)
        if a.settle:
            m, _ = settle(m)
        r = drop_test(m, a.trials, a.height, a.tilt, a.shove)
        for run in r["runs"]:
            run.pop("pose")
        print(json.dumps(r, indent=2, default=float))
    elif a.cmd == "stand":
        _stand(a, profile)
    elif a.cmd == "figure":
        _figure(a.out, profile)
    elif a.cmd == "burrito":
        from .sources import burritos

        os.makedirs(a.out, exist_ok=True)
        fig = burritos.figure(burritos.load(a.kind, hero=not a.no_hero), profile, a.mm, a.slots)
        stem = os.path.join(a.out, f"burrito-{fig.info['kind']}")
        write_stl(fig.solid, stem + ".stl")
        write_3mf(fig.colours, stem + ".3mf", assembly=fig.name)
        render([(m, c) for _, m, c in fig.colours], stem + ".png", azimuth=-70, elevation=20)
        print(f"wrote {stem}.stl / .3mf / .png")
        _provenance(stem, fig.info, fig.solid)


def _jointed(a, profile) -> None:
    from .motion import check_poses, posed, report
    from .orient import lay_flat
    from .sources import rabbitstew
    from .sources.rabbitstew_jointed import jointed

    os.makedirs(a.out, exist_ok=True)
    champ = rabbitstew.load(a.run, a.kind, a.gen)
    fig, info = jointed(champ, profile, a.mm)
    laid, layout = lay_flat(fig.solids)
    stem = os.path.join(a.out, f"jointed-{champ.name}")
    _emit(list(laid.items()), stem)
    ends = {j.name: check_poses(fig, j, 2)[-1] for j in fig.joints}  # every joint at the end of its range
    render([(m, PALETTE[i % len(PALETTE)]) for i, m in enumerate(posed(fig, ends).values())], stem + "-posed.png")
    with open(stem + ".json", "w") as f:
        json.dump(dict(info, checks=report(fig), layout=layout), f, indent=2, default=str)
    print(f"wrote {stem}.json / -posed.png")


def _stand(a, profile) -> None:
    from .sources import rabbitstew
    from .sources.rabbitstew_jointed import jointed
    from .stability import stand_search

    os.makedirs(a.out, exist_ok=True)
    champ = rabbitstew.load(a.run, a.kind, a.gen)
    fig, _ = jointed(champ, profile)
    r = stand_search(fig)
    best = r.pop("best_solid")
    stem = os.path.join(a.out, f"stand-{champ.name}")
    render([(best, PALETTE[0])], stem + ".png", elevation=12)
    with open(stem + ".json", "w") as f:
        json.dump(r, f, indent=2, default=float)
    print(json.dumps({k: v for k, v in r.items() if k != "settle_deg"}, default=float))


def _figure(out: str, profile) -> None:
    from . import figures
    from .accessories import accessories, wand

    os.makedirs(out, exist_ok=True)
    parts = figures.figure(profile)
    colours = {"head": "#f2d9a8", "torso": "#2f6fff", "arm-left": "#2f6fff", "arm-right": "#2f6fff",
               "hips": "#3a3a48", "leg-left": "#3a3a48", "leg-right": "#3a3a48"}
    plate = figures.plate_layout({n: [(n, m, colours[n])] for n, m in parts.items()})
    stem = os.path.join(out, f"figure-{profile.name}")
    write_stl([m for _, m, _ in plate], stem + ".stl")
    write_3mf(plate, stem + ".3mf")
    render([(m, c) for _, m, c in plate], stem + ".png", elevation=55)
    acc = figures.plate_layout(accessories(profile))
    astem = os.path.join(out, f"accessories-{profile.name}")
    write_stl([m for _, m, _ in acc], astem + ".stl")
    write_3mf(acc, astem + ".3mf")
    render([(m, c) for _, m, c in acc], astem + ".png", elevation=55)
    # Assembled, right arm raised, holding the wand upright in its hand.
    L = figures.Layout(profile)
    held = [(m.rotate([90, 0, 0]).translate(figures.hand_centre(profile, -1) + [0, 9.5, 0]), c)
            for _, m, c in wand(profile)]
    scene = [(figures.rotate_about_x(m, -90, L.shoulder) if n == "arm-right" else m, colours[n]) for n, m in parts.items()]
    scene += [(figures.rotate_about_x(m, -90, L.shoulder), c) for m, c in held]
    render(scene, os.path.join(out, "figure-assembled.png"), azimuth=-60, elevation=15)
    write_stl([m for m, _ in scene], os.path.join(out, "figure-assembled.stl"))  # posed, for printshop drop
    print(f"wrote {stem}.stl / .3mf / .png, {astem}.stl / .3mf / .png, figure-assembled.png / .stl")


def _provenance(stem: str, info: dict, body) -> None:
    info = dict(info, check=check(body).__dict__)
    with open(stem + ".json", "w") as f:
        json.dump(info, f, indent=2, default=float)
    print(json.dumps(info, default=float))


if __name__ == "__main__":
    main()
