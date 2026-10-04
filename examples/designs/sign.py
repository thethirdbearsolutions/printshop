"""sign: a printshop design. Run `printshop studio sign.py` and edit away."""
from printshop.figures import socket
from printshop.geom import box, cylinder

#: Each becomes a slider: (default, low, high, step).
PARAMS = {"studs": (4, 2, 8, 1), "height": (14.0, 6.0, 30.0, 0.5)}


def design(p, studs=4, height=14.0):
    """A sign that presses onto a row of studs. p is the printer profile: every fit comes from it."""
    studs = int(studs)
    w, d = studs * p.pitch - 2 * p.side_gap, 2 * p.pitch - 2 * p.side_gap
    base = box([w, d, p.plate_height], center=False).translate([-w / 2, -d / 2, 0])
    for i in range(studs - 1):  # sockets between the studs underneath, like a plate's tubes
        base -= socket(p, p.stud_height + 0.3).translate([(i + 1 - studs / 2) * p.pitch, 0, 0])
    board = box([w - 2, 2.4, height], center=False).translate([-(w - 2) / 2, -1.2, p.plate_height])
    knob = cylinder(2.0, 2.4).rotate([90, 0, 0]).translate([0, -1.2, p.plate_height + height / 2])
    return [("base", base, "#3a3a48"), ("board", board, "#f2d9a8"), ("knob", knob - board, "#c8323a")]
