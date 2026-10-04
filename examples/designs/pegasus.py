"""The Pegasus with its rider: sweep the wings, put the knight on or take it off."""
from printshop.pegasus import horse, wing
from printshop.scenes import rider as riding

PARAMS = {"wing_sweep": (25.0, -45.0, 45.0, 5.0), "rider": (1, 0, 1, 1)}


def design(p, wing_sweep=25.0, rider=1):
    if int(rider):
        return riding(p, sweep_deg=wing_sweep)
    return horse(p) + [(f"wing-{s}", wing(p, k, wing_sweep), "#cfe3ff") for s, k in (("left", 1), ("right", -1))]
