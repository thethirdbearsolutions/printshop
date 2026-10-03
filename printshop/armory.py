"""An armoury for the brick-system figure: sword, shield, helmet and armour.

Swords and shields are held by the bar (profile.pin_diameter), so any hand built for
that bar takes them. The helmet slides over the figure's domed head and grips the stud
on top of it; the armour is a yoke that drops over the neck stud, with a breastplate
and a backplate hanging in front of and behind the torso, and the head then holds it
down. Every piece is (name, Manifold, colour), shiny bits in their own colour, and is
built in place on the assembled figure where that makes sense (helmet, armour) or
standing on its own (sword, shield).
"""
from __future__ import annotations

from manifold3d import Manifold

from .accessories import bar, star
from .figures import DEPTH, HEAD_D, HEAD_H, TORSO_W, Layout, along_x, along_y, hand, span
from .geom import cylinder, sphere
from .profiles import FDM_04, Profile

STEEL, GOLD, LEATHER, RED = "#d8dce4", "#e8b030", "#6a4424", "#c8323a"
YOKE = 0.8  # how far the armour's yoke lifts the head


def sword(p: Profile = FDM_04, blade: float = 20.0) -> list:
    """Grip (the bar) from z = 0, a pommel under it, a crossguard and a pointed blade above."""
    grip_len, t = 9.0, max(p.min_wall, 1.2)
    pommel = sphere(1.9, 32).translate([0, 0, -1.2])
    grip = bar(p, grip_len) - pommel
    guard = span(-5.0, 5.0, -1.2, 1.2, grip_len, grip_len + 1.6)
    z0 = grip_len + 1.6
    edge = Manifold.batch_hull([span(-1.4, 1.4, -t / 2, t / 2, z0, z0 + 0.1),
                                span(-1.1, 1.1, -t / 2, t / 2, z0 + blade - 3.0, z0 + blade - 2.9),
                                span(-0.1, 0.1, -t / 2, t / 2, z0 + blade - 0.1, z0 + blade)])
    return [("sword-grip", grip, LEATHER), ("sword-hilt", pommel + guard, GOLD), ("sword-blade", edge, STEEL)]


def shield(p: Profile = FDM_04, r: float = 7.5) -> list:
    """A round shield facing -y, a star on its face; behind it a length of bar on two posts for a hand."""
    t = 1.4
    face = along_y(-t / 2, t / 2, r)
    rim = along_y(-t / 2 - 0.6, t / 2, r) - along_y(-t, t, r - 1.0)
    boss = star(3.6, 1.2).translate([0, -t / 2 - 0.5, 0])
    _, ro = hand(p)
    yb = t / 2 + ro + 0.4  # the bar's axis behind the face: room for a clip round it
    half = 3.2 / 2 + 1.2  # clip length plus room either side
    grip = bar(p, 2 * half + 2.0).translate([0, yb, -half - 1.0])
    posts = [span(-1.2, 1.2, t / 2 - 0.1, yb + 0.6, sz * (half + 0.5) - 0.6, sz * (half + 0.5) + 0.6) for sz in (1, -1)]
    body = face + grip + posts[0] + posts[1]
    trim = rim + boss
    return [("shield", body - trim, RED), ("shield-trim", trim, GOLD)]


def shield_bar_axis(p: Profile = FDM_04) -> float:
    """How far behind the shield's centre plane its bar runs (y)."""
    return 1.4 / 2 + hand(p)[1] + 0.4


def _dome(r: float, neck: float, top: float, bottom: float | None = None, rise: float = 0.0) -> Manifold:
    """The figure's head shape (seated at `neck`: a cylinder, a round top, a flat crown at `top`) grown
    to radius r, reaching down to `bottom`, its round top raised `rise`."""
    zc = neck + HEAD_H - HEAD_D / 2 + rise
    z0 = neck if bottom is None else bottom
    m = cylinder(zc - z0, r).translate([0, 0, z0]) + sphere(r, 64).translate([0, 0, zc])
    return m.trim_by_plane([0, 0, -1], -top)


def helmet(p: Profile = FDM_04, lift: float = YOKE) -> list:
    """A helm over the head (sitting `lift` up on armour), gripping the head's top stud, eye slit, crest."""
    L, g, w = Layout(p), p.joint_clearance, max(p.min_wall, 1.2)
    neck = L.neck + lift
    r, crown = HEAD_D / 2, neck + HEAD_H - 0.8
    hole = (p.stud_diameter + p.socket_delta + p.xy_compensation) / 2
    top = crown + p.stud_height + 0.2 + g + w  # room over the head's stud for a socket and a wall
    outer = _dome(r + g + w, neck, top, rise=top - (neck + HEAD_H - HEAD_D / 2 + r + g + w) + 1.0)
    inner = _dome(r + g, neck, crown + g, bottom=neck - 1)
    m = outer - inner - cylinder(p.stud_height + 0.2 + g, hole).translate([0, 0, crown])
    m = m.trim_by_plane([0, 0, 1], neck + 1.2)  # stops short of the shoulders
    m -= span(-3.4, 3.4, -r - 5, 0, neck + 4.0, neck + 5.4)  # eye slit
    crest = along_x(-0.8, 0.8, 4.5, z=top - 0.4).trim_by_plane([0, 0, 1], top - 0.4) - m  # a fin, front to back
    return [("helmet", m, STEEL), ("helmet-crest", crest, RED)]


def armour(p: Profile = FDM_04) -> list:
    """A yoke over the neck stud, with a breastplate (a gold star on it) and a backplate."""
    L, g, t = Layout(p), p.joint_clearance, max(p.min_wall, 1.0)
    w = TORSO_W / 2 - 0.6  # inside the arms
    hole = (p.stud_diameter + 0.2 + p.xy_compensation) / 2  # loose: the head clamps the yoke down
    yoke = span(-w, w, -DEPTH / 2 - g - t, DEPTH / 2 + g + t, L.neck, L.neck + YOKE)
    plates = [span(-w, w, DEPTH / 2 + g, DEPTH / 2 + g + t, L.neck - 7.0, L.neck + YOKE),
              span(-w, w, -DEPTH / 2 - g - t, -DEPTH / 2 - g, L.neck - 7.0, L.neck + YOKE)]
    body = (yoke + plates[0] + plates[1]) - cylinder(YOKE + 1, hole).translate([0, 0, L.neck - 0.5])
    emblem = star(2.6, 0.8).translate([0, -DEPTH / 2 - g - t - 0.39, L.neck - 3.4])
    return [("armour", body - emblem, STEEL), ("armour-star", emblem, GOLD)]


def armoury(p: Profile = FDM_04) -> dict:
    return {"sword": sword(p), "shield": shield(p), "helmet": helmet(p), "armour": armour(p)}
