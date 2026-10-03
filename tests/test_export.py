import struct
import zipfile

from printshop.bricks import plate
from printshop.export import write_3mf, write_stl


def test_stl_has_the_triangle_count_it_claims(tmp_path):
    path = tmp_path / "p.stl"
    n = write_stl(plate(2, 2), str(path))
    data = path.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] == n
    assert len(data) == 84 + 50 * n


def test_3mf_holds_each_object_with_its_colour(tmp_path):
    path = tmp_path / "p.3mf"
    write_3mf([("red", plate(1, 1), "#C8553D"), ("plain", plate(1, 2), None)], str(path))
    with zipfile.ZipFile(path) as z:
        model = z.read("3D/3dmodel.model").decode()
    assert model.count("<object ") == 2 and 'displaycolor="#C8553DFF"' in model
