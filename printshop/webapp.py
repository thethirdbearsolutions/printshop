"""printshop in the browser: a design page that runs printshop itself, with no server and no install.

    printshop web DESIGN.py OUT_DIR

writes a folder you can host anywhere (or open from a local web server): index.html is the studio
page in its in-browser mode, and py/ holds what Pyodide (Python compiled to WebAssembly) needs to
run printshop: the manifold3d wheel built by tools/pyodide/build.sh, Pyodide's own numpy and Pillow
wheels, and printshop's source as a zip. Pyodide itself loads from the jsdelivr CDN. Sliders,
the code editor and the downloads all run the design in the page.
"""
from __future__ import annotations

import glob
import io
import json
import os
import shutil
import urllib.request
import zipfile

from . import studio

PYODIDE = "0.29.5"
CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full/"
NPM = f"https://cdn.jsdelivr.net/npm/pyodide@{PYODIDE}/"  # the core runtime (no package wheels)
PACKAGES = ["numpy-2.2.5-cp313-cp313-pyemscripten_2025_0_wasm32.whl",
            "pillow-11.3.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHEELS = os.path.join(ROOT, "tools", "pyodide", "dist")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "printshop", f"pyodide-{PYODIDE}")


def _package(name: str) -> str:
    """A Pyodide package wheel, downloaded once into the cache."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        with urllib.request.urlopen(CDN + name) as r, open(path + ".part", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(path + ".part", path)
    return path


def source_zip() -> bytes:
    """printshop's own package (code, page, data), zipped for unpacking into Pyodide's site-packages."""
    buf = io.BytesIO()
    pkg = os.path.join(ROOT, "printshop")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d, _, files in os.walk(pkg):
            if "__pycache__" in d:
                continue
            for f in files:
                full = os.path.join(d, f)
                z.write(full, os.path.relpath(full, ROOT))
    return buf.getvalue()


def build(design: str, out: str, profile: str = "fdm-0.4") -> list:
    """Write the page and its files into `out`. Returns the files written, relative to `out`."""
    wheel = sorted(glob.glob(os.path.join(WHEELS, "manifold3d-*-pyemscripten_*_wasm32.whl")))
    if not wheel:
        raise FileNotFoundError(f"no manifold3d Pyodide wheel in {WHEELS}: run tools/pyodide/build.sh")
    os.makedirs(os.path.join(out, "py"), exist_ok=True)
    files = []
    for src in [wheel[-1]] + [_package(n) for n in PACKAGES]:
        shutil.copy(src, os.path.join(out, "py", os.path.basename(src)))
        files.append("py/" + os.path.basename(src))
    with open(os.path.join(out, "py", "printshop.zip"), "wb") as f:
        f.write(source_zip())
    files.append("py/printshop.zip")
    with open(design) as f:
        code = f.read()
    boot = {"engine": "pyodide", "pyodide": NPM, "wheels": [x for x in files if x.endswith(".whl")],
            "source_zip": "py/printshop.zip", "source": code}
    html = studio.page(design, static=True, profile=profile)
    html = html.replace('"live": false', '"live": false, ' + json.dumps(boot)[1:-1], 1)
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(html)
    return ["index.html"] + files


INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>printshop designs</title>
<style>
  :root {{ --bg: #f4f3ef; --card: #fff; --ink: #1d1d1f; --muted: #6b6b70; --line: #dddad2; --accent: #2f6fff; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
    --bg: #17181b; --card: #222429; --ink: #ececef; --muted: #9a9aa3; --line: #34363c; --accent: #6f9bff; }} }}
  :root[data-theme="dark"] {{ --bg: #17181b; --card: #222429; --ink: #ececef; --muted: #9a9aa3; --line: #34363c;
    --accent: #6f9bff; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 system-ui, sans-serif; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 32px 16px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }} p {{ color: var(--muted); margin: 0 0 24px; }}
  a.card {{ display: block; background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 14px 16px; margin-bottom: 12px; color: inherit; text-decoration: none; }}
  a.card:hover {{ border-color: var(--accent); }} .name {{ font-weight: 600; }} .doc {{ color: var(--muted); font-size: 13px; }}
</style></head>
<body><main><h1>printshop designs</h1>
<p>Each runs printshop itself in your browser: turn it, move its sliders, edit its code, download the STL.</p>
{cards}
</main></body></html>
"""


def site(designs: list, out: str, profile: str = "fdm-0.4") -> list:
    """A page per design (out/<name>/) and an index linking them: what GitHub Pages serves."""
    import ast
    import html

    cards, written = [], ["index.html"]
    for design in sorted(designs):
        name = os.path.splitext(os.path.basename(design))[0]
        written += [f"{name}/{f}" for f in build(design, os.path.join(out, name), profile)]
        with open(design) as f:
            doc = (ast.get_docstring(ast.parse(f.read())) or "").split("\n")[0]
        cards.append(f'<a class="card" href="{name}/"><div class="name">{html.escape(name)}</div>'
                     f'<div class="doc">{html.escape(doc)}</div></a>')
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(INDEX.format(cards="\n".join(cards)))
    return written
