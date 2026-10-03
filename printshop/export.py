"""Writing printable files: binary STL (one solid) and 3MF (several named, coloured objects)."""
from __future__ import annotations

import struct
import zipfile

import numpy as np
from manifold3d import Manifold


def _mesh_arrays(m: Manifold):
    mesh = m.to_mesh()
    return mesh.vert_properties[:, :3].astype(np.float32), np.asarray(mesh.tri_verts, dtype=np.int64)


def write_stl(parts, path: str, header: str = "printshop") -> int:
    """Write one or more solids into a binary STL; returns the triangle count."""
    if isinstance(parts, Manifold):
        parts = [parts]
    tris = []
    for m in parts:
        v, t = _mesh_arrays(m)
        tris.append(v[t])
    tri = np.concatenate(tris)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tri), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    with open(path, "wb") as f:
        f.write(header.encode()[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(tri)))
        f.write(rec.tobytes())
    return len(tri)


def write_3mf(objects, path: str) -> None:
    """objects: list of (name, Manifold, "#RRGGBB" or None). Each becomes its own object, so a
    multi-colour printer can give each its own filament and a slicer can arrange them."""
    colours = sorted({c for _, _, c in objects if c})
    cidx = {c: i for i, c in enumerate(colours)}
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
           "<resources>"]
    if colours:
        out.append('<basematerials id="1">' + "".join(
            f'<base name="c{i}" displaycolor="{c}FF"/>' for i, c in enumerate(colours)) + "</basematerials>")
    build = []
    for k, (name, m, colour) in enumerate(objects, start=2):
        v, t = _mesh_arrays(m)
        mat = f' pid="1" pindex="{cidx[colour]}"' if colour else ""
        out.append(f'<object id="{k}" name="{name}" type="model"{mat}><mesh><vertices>')
        out.append("".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in v))
        out.append("</vertices><triangles>")
        out.append("".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t))
        out.append("</triangles></mesh></object>")
        build.append(f'<item objectid="{k}"/>')
    out += ["</resources>", "<build>" + "".join(build) + "</build>", "</model>"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", "\n".join(out))
