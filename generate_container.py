#!/usr/bin/env python3
"""
Generate a multi-color 3MF that combines a container template (bayonet box)
with a QR code placed on its lid.

Output has two color groups for Bambu AMS:
  extruder 1 (green) — container body + lid
  extruder 2 (white) — QR code on lid top

Container and lid are laid out side by side, both flat on the build plate.
"""

import argparse
import hashlib
import os
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import trimesh

from generate_3d_qr import (
    OUTPUT_DIR,
    create_box_triangles,
    generate_qr_code,
    get_dimensions,
    qr_to_array,
)

CONTAINER_DIR = os.path.join(os.path.dirname(__file__), "containers")
DEFAULT_TEMPLATE = os.path.join(CONTAINER_DIR, "bayonetbox.3mf")

# Maps human-friendly variant names to (container_object, lid_object) filenames
# inside the template 3MF.
VARIANTS = {
    "large": {
        "container": "object_1.model",
        "lid": "object_2.model",
        "lid_radius": 40.5,
        "lid_top_z": 12.5,
        "lid_bottom_z": -12.5,
        "container_bottom_z": -25.5,
        "outer_radius": 42.5,
    },
    "small": {
        "container": "object_3.model",
        "lid": "object_4.model",
        "lid_radius": 37.5,
        "lid_top_z": 7.5,
        "lid_bottom_z": -7.5,
        "container_bottom_z": -15.5,
        "outer_radius": 39.5,
    },
}


def load_mesh_from_3mf_object(zip_path, object_filename):
    """Parse a 3MF object XML and return a trimesh.Trimesh."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        data = zf.read(f"3D/Objects/{object_filename}")

    root = ET.fromstring(data)
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}

    vertices = []
    for v in root.findall(".//m:vertex", ns):
        vertices.append([float(v.get("x")), float(v.get("y")), float(v.get("z"))])

    faces = []
    for t in root.findall(".//m:triangle", ns):
        faces.append([int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))])

    return trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces))


def build_qr_mesh(url, qr_size_mm, base_z, qr_height=0.9):
    """Build the white QR mesh at the given Z offset (no base plate, no text)."""
    qr_img = generate_qr_code(url, size=200)
    qr_array = qr_to_array(qr_img)

    dims = get_dimensions(qr_size_mm)
    pixel_size = dims["qr_size_mm"] / qr_array.shape[0]
    square_size = pixel_size * 0.95

    qr_triangles = []
    for i in range(qr_array.shape[0]):
        for j in range(qr_array.shape[1]):
            if qr_array[i, j] == 1:
                x = (j - qr_array.shape[1] / 2) * pixel_size
                y = (qr_array.shape[0] / 2 - i) * pixel_size
                qr_triangles.extend(
                    create_box_triangles(x, y, base_z, square_size, square_size, qr_height)
                )

    qr_triangles = np.array(qr_triangles)
    qr_vertices = qr_triangles.reshape(-1, 3)
    qr_faces = np.arange(len(qr_vertices)).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=qr_vertices, faces=qr_faces)
    mesh.merge_vertices()
    return mesh


def mesh_to_verts_tris_xml(mesh_obj, material_index):
    """Serialize a trimesh to 3MF vertex/triangle XML fragments."""
    verts_xml = ""
    for v in mesh_obj.vertices:
        verts_xml += f'          <vertex x="{v[0]:.6f}" y="{v[1]:.6f}" z="{v[2]:.6f}" />\n'

    tris_xml = ""
    for f in mesh_obj.faces:
        tris_xml += f'          <triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}" pid="1" p1="{material_index}" />\n'

    return verts_xml, tris_xml


def generate_container(url, output_file, template=DEFAULT_TEMPLATE, variant="large", qr_size=None):
    """Main entry: load container + lid, generate QR, write combined 3MF.

    Produces exactly the same 3MF structure as the working QR plates:
    one composite build item containing mesh parts with pid/p1 material refs.
    Container and lid are separate objects so they can be individually deleted.
    """
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant {variant!r}; choose from {list(VARIANTS)}")

    spec = VARIANTS[variant]

    lid_diameter = spec["lid_radius"] * 2
    if qr_size is None:
        qr_size_mm = min(lid_diameter * 0.75, 60)
    else:
        qr_size_mm = qr_size

    print(f"  Loading container template ({variant})…")
    container_mesh = load_mesh_from_3mf_object(template, spec["container"])
    lid_mesh = load_mesh_from_3mf_object(template, spec["lid"])

    # Shift both to Z=0 (bottom on build plate)
    container_mesh.vertices[:, 2] -= spec["container_bottom_z"]
    lid_mesh.vertices[:, 2] -= spec["lid_bottom_z"]

    lid_top_z = spec["lid_top_z"] - spec["lid_bottom_z"]

    # Place lid beside container with a gap
    gap = 10
    x_offset = spec["outer_radius"] * 2 + gap
    lid_mesh.vertices[:, 0] += x_offset

    # Sink QR 0.3mm into the lid for proper color boundary
    qr_base_z = lid_top_z - 0.3
    print(f"  Generating QR ({qr_size_mm:.0f}mm) on lid top (Z={lid_top_z:.1f})…")
    qr_mesh = build_qr_mesh(url, qr_size_mm, base_z=qr_base_z)
    qr_mesh.vertices[:, 0] += x_offset

    container_verts, container_tris = mesh_to_verts_tris_xml(container_mesh, 0)
    lid_verts, lid_tris = mesh_to_verts_tris_xml(lid_mesh, 0)
    qr_verts, qr_tris = mesh_to_verts_tris_xml(qr_mesh, 1)

    model_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">
  <metadata name="Application">TreasureQR Generator</metadata>
  <resources>
    <m:basematerials id="1">
      <m:base name="Green" displaycolor="#00AA00" />
      <m:base name="White" displaycolor="#FFFFFF" />
    </m:basematerials>
    <object id="1" name="container" type="model">
      <mesh>
        <vertices>
{container_verts}        </vertices>
        <triangles>
{container_tris}        </triangles>
      </mesh>
    </object>
    <object id="2" name="lid" type="model">
      <mesh>
        <vertices>
{lid_verts}        </vertices>
        <triangles>
{lid_tris}        </triangles>
      </mesh>
    </object>
    <object id="3" name="qr_code" type="model">
      <mesh>
        <vertices>
{qr_verts}        </vertices>
        <triangles>
{qr_tris}        </triangles>
      </mesh>
    </object>
    <object id="4" name="container_group" type="model">
      <components>
        <component objectid="1" />
      </components>
    </object>
    <object id="5" name="lid_group" type="model">
      <components>
        <component objectid="2" />
        <component objectid="3" />
      </components>
    </object>
  </resources>
  <build>
    <item objectid="4" />
    <item objectid="5" />
  </build>
</model>'''

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />
  <Default Extension="config" ContentType="text/xml" />
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>'''

    model_settings_config = '''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="1">
    <metadata key="extruder" value="1"/>
    <metadata key="name" value="container"/>
  </object>
  <object id="2">
    <metadata key="extruder" value="1"/>
    <metadata key="name" value="lid"/>
  </object>
  <object id="3">
    <metadata key="extruder" value="2"/>
    <metadata key="name" value="qr_code"/>
  </object>
  <object id="4">
    <metadata key="name" value="container_group"/>
    <part id="1">
      <metadata key="extruder" value="1"/>
    </part>
  </object>
  <object id="5">
    <metadata key="name" value="lid_group"/>
    <part id="2">
      <metadata key="extruder" value="1"/>
    </part>
    <part id="3">
      <metadata key="extruder" value="2"/>
    </part>
  </object>
</config>'''

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", model_settings_config)

    print(f"✓ Created container 3MF: {output_file}")
    print("  Container and lid+QR are separate parts in the composite.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a container 3MF with QR code on the lid (Bambu AMS).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="URL to encode in QR code on the lid")
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output 3MF path (default: output/container_qr_<hash>.3mf)",
    )
    parser.add_argument(
        "-v", "--variant", choices=list(VARIANTS), default="large",
        help="Container size variant (default: large)",
    )
    parser.add_argument(
        "-s", "--size", default=None, type=float,
        help="QR code size in mm (default: auto-fit to lid ~75%%)",
    )
    parser.add_argument(
        "-t", "--template", default=DEFAULT_TEMPLATE,
        help="Path to container template 3MF (default: containers/bayonetbox.3mf)",
    )
    args = parser.parse_args()

    if args.output is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        url_hash = hashlib.md5(args.url.encode()).hexdigest()[:8]
        args.output = os.path.join(OUTPUT_DIR, f"container_qr_{url_hash}.3mf")

    generate_container(
        args.url, args.output,
        template=args.template,
        variant=args.variant,
        qr_size=args.size,
    )
