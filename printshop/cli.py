"""printshop command line.

    printshop card OUT_DIR [--profile fdm-0.4]          tolerance card: 2x2 plates sweeping stud/tube fit
    printshop brick WxL OUT.stl [--plates 3]             one brick (3 plates) or plate (1)
    printshop joints OUT_DIR [--profile fdm-0.4]         print-in-place hinge and ball joint test pieces
    printshop champion RUN KIND GEN OUT_DIR [--seed 3]   a rabbitstew champion posed on a plinth (needs the extra)
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
    a = ap.parse_args(argv)
    profile = PROFILES[a.profile]

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


def _provenance(stem: str, info: dict, body) -> None:
    info = dict(info, check=check(body).__dict__)
    with open(stem + ".json", "w") as f:
        json.dump(info, f, indent=2, default=float)
    print(json.dumps(info, default=float))


if __name__ == "__main__":
    main()
