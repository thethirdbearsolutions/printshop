import io
import json
import struct
import threading
import urllib.request
import zipfile

import pytest

from printshop import studio


@pytest.fixture
def design(tmp_path):
    path = tmp_path / "sign.py"
    studio.new(str(path))
    return path


def test_new_writes_a_design_that_runs_and_passes_its_checks(design):
    with pytest.raises(FileExistsError):
        studio.new(str(design))
    data = studio.payload(str(design))
    assert [p["name"] for p in data["parts"]] == ["base", "board", "knob"]
    assert data["checks"]["pieces"] == 1 and data["checks"]["stands"]
    assert studio.params_of(str(design)) == {"studs": [4, 2, 8, 1], "height": [14.0, 6.0, 30.0, 0.5]}


def test_sliders_change_the_model(design):
    narrow = studio.payload(str(design), params={"studs": 2})["checks"]["size_mm"][0]
    wide = studio.payload(str(design), params={"studs": 6})["checks"]["size_mm"][0]
    assert wide - narrow == pytest.approx(4 * 8.0, abs=0.01)  # four more studs, a pitch each


def test_a_broken_design_reports_its_error_instead_of_crashing(design):
    design.write_text(design.read_text().replace("return [", "return oops + ["))
    data = studio.payload(str(design))
    assert "NameError" in data["error"] and "oops" in data["error"]


def test_a_design_may_return_a_bare_solid(tmp_path):
    path = tmp_path / "cube.py"
    path.write_text("from printshop.geom import box\ndef design(p):\n    return box([10, 10, 10], center=False)\n")
    assert studio.parts(str(path))[0][0] == "part"


def test_snapshot_page_carries_the_model(design):
    html = studio.page(str(design), static=True)
    boot = json.loads(html.split("const BOOT = ")[1].split(";\n")[0])
    assert not boot["live"] and boot["model"]["checks"]["pieces"] == 1 and "studs" in boot["params"]


def test_live_server_serves_the_page_the_model_and_downloads(design):
    server = studio.make_server(str(design), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    assert b"printshop studio" in urllib.request.urlopen(base + "/").read()
    model = json.loads(urllib.request.urlopen(base + "/model?params=%7B%22studs%22%3A3%7D").read())
    assert model["checks"]["size_mm"][0] == pytest.approx(3 * 8.0 - 0.2, abs=0.01)
    stl = urllib.request.urlopen(base + "/download.stl").read()
    assert len(stl) == 84 + 50 * struct.unpack("<I", stl[80:84])[0]
    mf = urllib.request.urlopen(base + "/download.3mf").read()
    with zipfile.ZipFile(io.BytesIO(mf)) as z:
        assert z.read("3D/3dmodel.model").count(b"<component ") == 3
    server.shutdown()
