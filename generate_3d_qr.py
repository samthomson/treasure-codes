#!/usr/bin/env python3
"""
Generate 3D printable QR codes with embossed text for Bambu printers.
Multi-color: Green base with white QR code squares.

Usage:
    python generate_3d_qr.py <url> [output.3mf] [size]
    
Size presets: small (40mm), medium (50mm), large (60mm), or any number in mm
"""

import os
import qrcode
from PIL import Image
import numpy as np
from stl import mesh

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

OUTPUT_DIR = "output"

# Size presets (QR code width in mm)
SIZE_PRESETS = {
    "small": 40,
    "medium": 50,
    "large": 60,
}


def generate_qr_code(url, size=200, border=4):
    """Generate a QR code image from a URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))
    return img


def qr_to_array(qr_image):
    """Convert QR code image to numpy array (0=white, 1=black/QR square)."""
    img_array = np.array(qr_image.convert('L'))
    binary = (img_array < 128).astype(int)
    return binary


def create_box_triangles(x, y, z, width, depth, height):
    """Create triangles for a box. Returns array of 12 triangles."""
    v = np.array([
        [x - width/2, y - depth/2, z],
        [x + width/2, y - depth/2, z],
        [x + width/2, y + depth/2, z],
        [x - width/2, y + depth/2, z],
        [x - width/2, y - depth/2, z + height],
        [x + width/2, y - depth/2, z + height],
        [x + width/2, y + depth/2, z + height],
        [x - width/2, y + depth/2, z + height],
    ])
    
    triangles = np.array([
        [v[0], v[2], v[1]], [v[0], v[3], v[2]],  # Bottom
        [v[4], v[5], v[6]], [v[4], v[6], v[7]],  # Top
        [v[0], v[1], v[5]], [v[0], v[5], v[4]],  # Front
        [v[2], v[3], v[7]], [v[2], v[7], v[6]],  # Back
        [v[0], v[4], v[7]], [v[0], v[7], v[3]],  # Left
        [v[1], v[2], v[6]], [v[1], v[6], v[5]],  # Right
    ])
    return triangles


def get_dimensions(qr_size_mm):
    """Calculate all dimensions scaled proportionally from qr_size_mm."""
    scale = qr_size_mm / 42  # 42mm was the tuned reference size
    return {
        "qr_size_mm": qr_size_mm,
        "margin": 2 * scale,
        "text_area_height": 5 * scale,
        "corner_radius": 2.5 * scale,
        "text_size": 4.2 * scale,
        "text_y_offset": 1.8 * scale,
    }


def create_3d_qr_code_combined(url, output_file, qr_size_mm=50, base_height=1.8, qr_height=0.9, text_height=1.2):
    """
    Create a single STL file with base + QR pattern combined.
    Use filament change at Z=base_height for two colors (for non-AMS printers).
    """
    print("  Generating QR code...")
    qr_img = generate_qr_code(url, size=200)
    qr_array = qr_to_array(qr_img)
    
    dims = get_dimensions(qr_size_mm)
    pixel_size = dims["qr_size_mm"] / qr_array.shape[0]
    total_height = dims["text_area_height"] + dims["qr_size_mm"] + 2 * dims["margin"]
    total_width = dims["qr_size_mm"] + 2 * dims["margin"]
    
    print(f"  Model size: {total_width:.1f}mm x {total_height:.1f}mm")
    print("  Building mesh...")
    all_triangles = []
    
    # Base plate with rounded corners (using CadQuery)
    if CADQUERY_AVAILABLE:
        print("  Creating rounded base...")
        base_cq = (cq.Workplane("XY")
            .box(total_width, total_height, base_height)
            .edges("|Z")
            .fillet(dims["corner_radius"])
            .translate((0, 0, base_height/2))  # Move up so bottom is at Z=0
        )
        # Export to temp STL and read triangles
        import tempfile
        temp = tempfile.NamedTemporaryFile(suffix='.stl', delete=False)
        temp.close()
        cq.exporters.export(base_cq, temp.name)
        base_stl = mesh.Mesh.from_file(temp.name)
        os.unlink(temp.name)
        for vec in base_stl.vectors:
            all_triangles.append(vec)
    else:
        # Fallback to square corners
        base_triangles = create_box_triangles(0, 0, 0, total_width, total_height, base_height)
        all_triangles.extend(base_triangles)
    
    # QR squares
    qr_offset_y = -dims["text_area_height"] / 2
    square_size = pixel_size * 0.95
    square_count = 0
    
    for i in range(qr_array.shape[0]):
        for j in range(qr_array.shape[1]):
            if qr_array[i, j] == 1:
                x = (j - qr_array.shape[1]/2) * pixel_size
                y = (qr_array.shape[0]/2 - i) * pixel_size + qr_offset_y
                square_triangles = create_box_triangles(x, y, base_height, square_size, square_size, qr_height)
                all_triangles.extend(square_triangles)
                square_count += 1
    
    print(f"  Created {square_count} QR squares...")
    
    all_triangles = np.array(all_triangles)
    
    print(f"  Creating STL with {len(all_triangles)} triangles...")
    qr_mesh = mesh.Mesh(np.zeros(len(all_triangles), dtype=mesh.Mesh.dtype))
    for i, tri in enumerate(all_triangles):
        qr_mesh.vectors[i] = tri
    
    text_y = total_height/2 - dims["text_area_height"]/2 - dims["text_y_offset"]
    
    if CADQUERY_AVAILABLE:
        print("  Adding text 'https://treasures.to'...")
        try:
            import tempfile
            
            text_obj = cq.Workplane("XY").workplane(offset=base_height).center(0, text_y).text(
                "https://treasures.to", dims["text_size"], text_height, font="Arial", kind="bold"
            )
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.stl', delete=False)
            temp_file.close()
            cq.exporters.export(text_obj, temp_file.name)
            
            text_mesh = mesh.Mesh.from_file(temp_file.name)
            os.unlink(temp_file.name)
            
            combined_mesh = mesh.Mesh(np.concatenate([qr_mesh.data, text_mesh.data]))
            combined_mesh.save(output_file)
            print(f"✓ Created combined model with text: {output_file}")
        except Exception as e:
            print(f"  Warning: Could not add text ({e})")
            qr_mesh.save(output_file)
    else:
        qr_mesh.save(output_file)
        print(f"✓ Created model: {output_file}")


def create_3d_qr_code_multicolor(url, output_file, qr_size_mm=50, base_height=1.8, qr_height=0.9, text_height=1.2):
    """
    Create a 3MF file with two separate colored meshes for Bambu AMS.
    - Base mesh (green)
    - QR + text mesh (white)
    """
    import trimesh
    import zipfile
    
    print("  Generating QR code...")
    qr_img = generate_qr_code(url, size=200)
    qr_array = qr_to_array(qr_img)
    
    dims = get_dimensions(qr_size_mm)
    pixel_size = dims["qr_size_mm"] / qr_array.shape[0]
    total_height = dims["text_area_height"] + dims["qr_size_mm"] + 2 * dims["margin"]
    total_width = dims["qr_size_mm"] + 2 * dims["margin"]
    
    print(f"  Model size: {total_width:.1f}mm x {total_height:.1f}mm")
    print("  Building base mesh (green) with rounded corners...")
    
    # Base mesh with rounded corners (using CadQuery)
    if CADQUERY_AVAILABLE:
        import tempfile
        base_cq = (cq.Workplane("XY")
            .box(total_width, total_height, base_height)
            .edges("|Z")
            .fillet(dims["corner_radius"])
            .translate((0, 0, base_height/2))  # Move up so bottom is at Z=0
        )
        temp = tempfile.NamedTemporaryFile(suffix='.stl', delete=False)
        temp.close()
        cq.exporters.export(base_cq, temp.name)
        base_mesh = trimesh.load(temp.name)
        os.unlink(temp.name)
    else:
        # Fallback to square corners
        base_triangles = np.array(create_box_triangles(0, 0, 0, total_width, total_height, base_height))
        base_vertices = base_triangles.reshape(-1, 3)
        base_faces = np.arange(len(base_vertices)).reshape(-1, 3)
        base_mesh = trimesh.Trimesh(vertices=base_vertices, faces=base_faces)
        base_mesh.merge_vertices()
    
    print("  Building QR pattern mesh (white)...")
    
    # QR squares mesh
    qr_offset_y = -dims["text_area_height"] / 2
    square_size = pixel_size * 0.95
    qr_triangles = []
    
    for i in range(qr_array.shape[0]):
        for j in range(qr_array.shape[1]):
            if qr_array[i, j] == 1:
                x = (j - qr_array.shape[1]/2) * pixel_size
                y = (qr_array.shape[0]/2 - i) * pixel_size + qr_offset_y
                square_triangles = create_box_triangles(x, y, base_height, square_size, square_size, qr_height)
                qr_triangles.extend(square_triangles)
    
    qr_triangles = np.array(qr_triangles)
    qr_vertices = qr_triangles.reshape(-1, 3)
    qr_faces = np.arange(len(qr_vertices)).reshape(-1, 3)
    qr_mesh = trimesh.Trimesh(vertices=qr_vertices, faces=qr_faces)
    qr_mesh.merge_vertices()
    
    text_y = total_height/2 - dims["text_area_height"]/2 - dims["text_y_offset"]
    
    if CADQUERY_AVAILABLE:
        print("  Adding text mesh...")
        try:
            import tempfile
            
            text_obj = cq.Workplane("XY").workplane(offset=base_height).center(0, text_y).text(
                "https://treasures.to", dims["text_size"], text_height, font="Arial", kind="bold"
            )
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.stl', delete=False)
            temp_file.close()
            cq.exporters.export(text_obj, temp_file.name)
            
            text_mesh = trimesh.load(temp_file.name)
            os.unlink(temp_file.name)
            
            qr_mesh = trimesh.util.concatenate([qr_mesh, text_mesh])
        except Exception as e:
            print(f"  Warning: Could not add text ({e})")
    
    print("  Creating 3MF with embedded color assignments...")
    
    def mesh_to_3mf_xml(mesh_obj, object_id):
        verts = mesh_obj.vertices
        faces = mesh_obj.faces
        
        vertices_xml = ""
        for v in verts:
            vertices_xml += f'          <vertex x="{v[0]:.6f}" y="{v[1]:.6f}" z="{v[2]:.6f}" />\n'
        
        triangles_xml = ""
        for f in faces:
            triangles_xml += f'          <triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}" pid="1" p1="{object_id-1}" />\n'
        
        return vertices_xml, triangles_xml
    
    base_verts, base_tris = mesh_to_3mf_xml(base_mesh, 1)
    qr_verts, qr_tris = mesh_to_3mf_xml(qr_mesh, 2)
    
    model_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">
  <metadata name="Application">TreasureQR Generator</metadata>
  <resources>
    <m:basematerials id="1">
      <m:base name="Green" displaycolor="#00AA00" />
      <m:base name="White" displaycolor="#FFFFFF" />
    </m:basematerials>
    <object id="1" name="base_green" type="model">
      <mesh>
        <vertices>
{base_verts}        </vertices>
        <triangles>
{base_tris}        </triangles>
      </mesh>
    </object>
    <object id="2" name="qr_white" type="model">
      <mesh>
        <vertices>
{qr_verts}        </vertices>
        <triangles>
{qr_tris}        </triangles>
      </mesh>
    </object>
    <object id="3" name="treasure_qr" type="model">
      <components>
        <component objectid="1" />
        <component objectid="2" />
      </components>
    </object>
  </resources>
  <build>
    <item objectid="3" />
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
    <metadata key="name" value="base_green"/>
  </object>
  <object id="2">
    <metadata key="extruder" value="2"/>
    <metadata key="name" value="qr_white"/>
  </object>
  <object id="3">
    <metadata key="name" value="treasure_qr"/>
    <part id="1">
      <metadata key="extruder" value="1"/>
    </part>
    <part id="2">
      <metadata key="extruder" value="2"/>
    </part>
  </object>
</config>'''
    
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types_xml)
        zf.writestr('_rels/.rels', rels_xml)
        zf.writestr('3D/3dmodel.model', model_xml)
        zf.writestr('Metadata/model_settings.config', model_settings_config)
    
    print(f"✓ Created multi-color 3MF: {output_file}")


def parse_size(size_arg):
    """Parse size argument - can be preset name or number in mm."""
    if size_arg in SIZE_PRESETS:
        return SIZE_PRESETS[size_arg]
    try:
        return float(size_arg)
    except ValueError:
        print(f"Unknown size '{size_arg}'. Using 50mm")
        return 50


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python generate_3d_qr.py <url> [output.3mf] [size]")
        print("\nSize options:")
        print("  small  = 40mm")
        print("  medium = 50mm")
        print("  large  = 60mm")
        print("  Or any number in mm (e.g. 45)")
        print("\nExamples:")
        print("  python generate_3d_qr.py 'https://treasures.to/abc' output.3mf medium")
        print("  python generate_3d_qr.py 'https://treasures.to/abc' output.3mf 55")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Parse output file
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_file = os.path.join(OUTPUT_DIR, f"treasure_qr_{url.split('/')[-1][:20]}.3mf")
    
    # Parse size
    qr_size_mm = 50
    if len(sys.argv) > 3:
        qr_size_mm = parse_size(sys.argv[3])
    
    # Generate based on file extension
    if output_file.endswith('.stl'):
        create_3d_qr_code_combined(url, output_file, qr_size_mm=qr_size_mm)
        print(f"\n✓ Single STL created: {output_file}")
        print(f"  Use 'Change filament at layer' at Z=1.8mm for two colors")
    else:
        if not output_file.endswith('.3mf'):
            output_file += '.3mf'
        create_3d_qr_code_multicolor(url, output_file, qr_size_mm=qr_size_mm)
        print(f"\n✓ Multi-color 3MF created: {output_file}")
        print("  Open in Bambu Studio - colors pre-assigned!")
