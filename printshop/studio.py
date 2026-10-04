"""printshop studio: a design file, a live 3D view, sliders for its parameters.

A design file is a Python file with a `design(p, **params)` function that returns the
print: one Manifold, a list of (name, Manifold, "#rrggbb") parts, or a dict of either.
It may declare PARAMS = {"name": (default, low, high, step), ...}; each becomes a slider.

    printshop new NAME          start a design file from a template
    printshop studio FILE       serve a live view: edit and save the file, the view follows
    printshop view FILE OUT     the same view as one standalone HTML page, nothing to serve

The page shows the model first; the sliders, the checks (one piece? stands? size) and the
printer profile are each a click further in. The viewer is the same page in both modes, so
it is also the shell a browser-only (Pyodide) printshop would sit in.
"""
from __future__ import annotations

import base64
import http.server
import json
import os
import runpy
import tempfile
import traceback
import urllib.parse

import numpy as np
from manifold3d import Manifold, OpType

from .checks import check
from .export import write_3mf, write_stl
from .preview import PALETTE
from .profiles import PROFILES

PAGE = os.path.join(os.path.dirname(__file__), "studio.html")
TEMPLATE = '''"""{name}: a printshop design. Run `printshop studio {file}` and edit away."""
from printshop.figures import socket
from printshop.geom import box, cylinder

#: Each becomes a slider: (default, low, high, step).
PARAMS = {{"studs": (4, 2, 8, 1), "height": (14.0, 6.0, 30.0, 0.5)}}


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
'''


def new(path: str) -> None:
    name = os.path.splitext(os.path.basename(path))[0]
    if os.path.exists(path):
        raise FileExistsError(path)
    with open(path, "w") as f:
        f.write(TEMPLATE.format(name=name, file=os.path.basename(path)))


def params_of(path: str) -> dict:
    ns = runpy.run_path(path)
    return {k: list(v) if isinstance(v, (tuple, list)) else [v] for k, v in ns.get("PARAMS", {}).items()}


def parts(path: str, profile: str = "fdm-0.4", params: dict | None = None) -> list:
    """Run the design: [(name, Manifold, colour)]."""
    ns = runpy.run_path(path)  # fresh every time, so edits show
    out = ns["design"](PROFILES[profile], **(params or {}))
    if isinstance(out, Manifold):
        out = [("part", out, None)]
    elif isinstance(out, dict):
        out = [(k, *(v if isinstance(v, tuple) else (v, None))) for k, v in out.items()]
    return [(n, m, c or PALETTE[i % len(PALETTE)]) for i, (n, m, c) in enumerate(out)]


def _b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def payload(path: str, profile: str = "fdm-0.4", params: dict | None = None) -> dict:
    """What the page draws: meshes, colours, checks, or the error the design raised."""
    try:
        got = parts(path, profile, params)
    except Exception:  # the design is being edited: show the error, keep the last good model on screen
        return {"error": traceback.format_exc(limit=6)}
    meshes = []
    for name, m, colour in got:
        mesh = m.to_mesh()
        meshes.append({"name": name, "colour": colour,
                       "positions": _b64(mesh.vert_properties[:, :3].astype(np.float32)),
                       "indices": _b64(np.asarray(mesh.tri_verts, dtype=np.uint32))})
    r = check(Manifold.batch_boolean([m for _, m, _ in got], OpType.Add))
    report = {"pieces": r.pieces, "stands": r.stands, "size_mm": list(r.size_mm), "volume_cm3": r.volume_cm3,
              "stability_margin_mm": r.stability_margin_mm, "parts": [n for n, _, _ in got]}
    return {"parts": meshes, "checks": report}


def downloads(path: str, profile: str, params: dict, kind: str) -> bytes:
    """The design as an STL (one file, every part) or a 3MF (one object, a part per colour)."""
    got = parts(path, profile, params)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, f"design.{kind}")
        if kind == "stl":
            write_stl([m for _, m, _ in got], out)
        else:
            write_3mf(got, out, assembly=os.path.splitext(os.path.basename(path))[0])
        with open(out, "rb") as f:
            return f.read()


def page(path: str, static: bool = False, profile: str = "fdm-0.4") -> str:
    """The viewer. static=True embeds the model and needs no server (sliders are then shown, not live)."""
    with open(PAGE) as f:
        html = f.read()
    boot = {"live": not static, "title": os.path.basename(path), "params": params_of(path),
            "profiles": list(PROFILES), "profile": profile}
    if static:
        boot["model"] = payload(path, profile)
    return html.replace("/*BOOT*/null", json.dumps(boot))


def make_server(path: str, port: int = 8008) -> http.server.ThreadingHTTPServer:
    """The live view's server on localhost (port 0: any free port)."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body: bytes, kind: str, name: str | None = None):
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            if name:
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            url = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            profile = q.pop("profile", "fdm-0.4")
            params = json.loads(q.get("params", "{}"))
            stem = os.path.splitext(os.path.basename(path))[0]
            if url.path == "/":
                self._send(page(path).encode(), "text/html; charset=utf-8")
            elif url.path == "/version":
                self._send(json.dumps({"mtime": os.path.getmtime(path), "params": params_of(path)}).encode(),
                           "application/json")
            elif url.path == "/model":
                self._send(json.dumps(payload(path, profile, params)).encode(), "application/json")
            elif url.path in ("/download.stl", "/download.3mf"):
                kind = url.path.rsplit(".", 1)[1]
                self._send(downloads(path, profile, params, kind), "application/octet-stream", f"{stem}.{kind}")
            else:
                self.send_error(404)

    return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(path: str, port: int = 8008) -> None:
    """Serve the live view on localhost until interrupted."""
    server = make_server(path, port)
    print(f"printshop studio: {path} at http://127.0.0.1:{port}/  (save the file to update; Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

