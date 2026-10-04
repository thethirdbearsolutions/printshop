import json
import os
import subprocess
import sys
import zipfile

import pytest

from printshop import webapp

needs_wheel = pytest.mark.skipif(not os.path.isdir(webapp.WHEELS) or not os.listdir(webapp.WHEELS),
                                 reason="no Pyodide wheel: tools/pyodide/build.sh")


def test_source_zip_is_an_importable_printshop(tmp_path):
    (tmp_path / "p.zip").write_bytes(webapp.source_zip())
    with zipfile.ZipFile(tmp_path / "p.zip") as z:
        names = z.namelist()
        z.extractall(tmp_path / "site")
    assert "printshop/studio.html" in names and not any("__pycache__" in n for n in names)
    assert any(n.startswith("printshop/data/burritos/") for n in names)
    design = os.path.join(os.path.dirname(__file__), "..", "examples", "designs", "sign.py")
    code = f"import json; from printshop import studio; print(json.dumps(studio.payload({design!r})['checks']))"
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path / "site", capture_output=True, text=True,
                         env=dict(os.environ, PYTHONPATH=str(tmp_path / "site")), check=True)
    assert json.loads(out.stdout)["pieces"] == 1


@needs_wheel
def test_build_writes_a_page_that_boots_python(tmp_path, monkeypatch):
    for name in webapp.PACKAGES:  # stand-ins: the real ones download from the Pyodide CDN
        (tmp_path / name).write_bytes(b"wheel")
    monkeypatch.setattr(webapp, "CACHE", str(tmp_path))
    design = os.path.join(os.path.dirname(__file__), "..", "examples", "designs", "sign.py")
    files = webapp.build(design, str(tmp_path / "site"))
    assert files[0] == "index.html" and "py/printshop.zip" in files
    assert any(f.startswith("py/manifold3d-") and f.endswith("_wasm32.whl") for f in files)
    html = (tmp_path / "site" / "index.html").read_text()
    boot = json.loads(html.split("const BOOT = ")[1].split(";\n")[0])
    assert boot["engine"] == "pyodide" and boot["pyodide"].startswith("https://cdn.jsdelivr.net/npm/pyodide@")
    assert "def design(p" in boot["source"] and boot["model"]["checks"]["pieces"] == 1  # a snapshot until it boots
    assert all((tmp_path / "site" / f).exists() for f in files)


@needs_wheel
def test_site_has_a_page_per_design_and_an_index(tmp_path, monkeypatch):
    for name in webapp.PACKAGES:
        (tmp_path / name).write_bytes(b"wheel")
    monkeypatch.setattr(webapp, "CACHE", str(tmp_path))
    designs = os.path.join(os.path.dirname(__file__), "..", "examples", "designs")
    files = webapp.site([os.path.join(designs, "sign.py")], str(tmp_path / "site"))
    assert "index.html" in files and "sign/index.html" in files
    index = (tmp_path / "site" / "index.html").read_text()
    assert 'href="sign/"' in index and "a printshop design" in index
