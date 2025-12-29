#!/usr/bin/env python3
"""
Generate 3D printable QR codes with embossed text for Bambu printers.
Multi-color: Green base with white QR code squares.

Usage:
    python generate_3d_qr.py <url> [output.3mf]   # Multi-color 3MF for AMS
    python generate_3d_qr.py <url> output.stl     # Single STL (filament change)
"""

import os
import qrcode
from PIL import Image
import numpy as np
from stl import mesh

# CadQuery is optional - only needed for text
try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

# Default output directory
OUTPUT_DIR = "output"


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


def create_3d_qr_code_combined(url, output_file, base_height=3, qr_height=1.5, text_height=2):
    """
    Create a single STL file with base + QR pattern combined.
    Use filament change at Z=3mm for two colors (for non-AMS printers).
    """
    print("  Generating QR code...")
    qr_img = generate_qr_code(url, size=200)
    qr_array = qr_to_array(qr_img)
    
    # Dimensions - compact layout
    qr_size_mm = 70
    pixel_size = qr_size_mm / qr_array.shape[0]
    text_area_height = 8  # Minimal gap - text sits close to QR
    margin = 3  # Reduced padding around edges
    corner_radius = 4  # Rounded corners
    total_height = text_area_height + qr_size_mm + 2 * margin
    total_width = qr_size_mm + 2 * margin
    
    print("  Building mesh...")
    all_triangles = []
    
    # Base plate with rounded corners (using CadQuery)
    if CADQUERY_AVAILABLE:
        print("  Creating rounded base...")
        base_cq = (cq.Workplane("XY")
            .box(total_width, total_height, base_height)
            .edges("|Z")
            .fillet(corner_radius)
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
    qr_offset_y = -text_area_height / 2
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
    
    # Add text if CadQuery available
    text_y = total_height/2 - text_area_height/2 - 3.0  # Moved down for equal padding
    text_size = 7.0  # Smaller text for 8mm area
    
    if CADQUERY_AVAILABLE:
        print("  Adding text 'https://treasures.to'...")
        try:
            import tempfile
            
            text_obj = cq.Workplane("XY").workplane(offset=base_height).center(0, text_y).text(
                "https://treasures.to", text_size, text_height, font="Arial", kind="bold"
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


def create_3d_qr_code_multicolor(url, output_file, base_height=3, qr_height=1.5, text_height=2):
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
    
    # Dimensions - compact layout
    qr_size_mm = 70
    pixel_size = qr_size_mm / qr_array.shape[0]
    text_area_height = 8  # Minimal gap - text sits close to QR
    margin = 3  # Reduced padding around edges
    corner_radius = 4  # Rounded corners
    total_height = text_area_height + qr_size_mm + 2 * margin
    total_width = qr_size_mm + 2 * margin
    
    print("  Building base mesh (green) with rounded corners...")
    
    # Base mesh with rounded corners (using CadQuery)
    if CADQUERY_AVAILABLE:
        import tempfile
        base_cq = (cq.Workplane("XY")
            .box(total_width, total_height, base_height)
            .edges("|Z")
            .fillet(corner_radius)
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
    qr_offset_y = -text_area_height / 2
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
    
    # Add text if CadQuery available
    text_y = total_height/2 - text_area_height/2 - 3.0  # Moved down for equal padding
    text_size = 7.0  # Smaller text for 8mm area
    
    if CADQUERY_AVAILABLE:
        print("  Adding text mesh...")
        try:
            import tempfile
            
            text_obj = cq.Workplane("XY").workplane(offset=base_height).center(0, text_y).text(
                "https://treasures.to", text_size, text_height, font="Arial", kind="bold"
            )
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.stl', delete=False)
            temp_file.close()
            cq.exporters.export(text_obj, temp_file.name)
            
            text_mesh = trimesh.load(temp_file.name)
            os.unlink(temp_file.name)
            
            qr_mesh = trimesh.util.concatenate([qr_mesh, text_mesh])
        except Exception as e:
            print(f"  Warning: Could not add text ({e})")
    
    # Create 3MF with embedded colors
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
  </resources>
  <build>
    <item objectid="1" />
    <item objectid="2" />
  </build>
</model>'''
    
    content_types_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />
</Types>'''
    
    rels_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>'''
    
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types_xml)
        zf.writestr('_rels/.rels', rels_xml)
        zf.writestr('3D/3dmodel.model', model_xml)
    
    print(f"✓ Created multi-color 3MF: {output_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Multi-color 3MF (AMS):  python generate_3d_qr.py <url> [output.3mf]")
        print("  Single STL (no AMS):    python generate_3d_qr.py <url> output.stl")
        print("\nExamples:")
        print("  python generate_3d_qr.py 'https://treasures.to/abc123'")
        print("  python generate_3d_qr.py 'https://treasures.to/abc123' my_qr.3mf")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Determine output file
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Default to output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_file = os.path.join(OUTPUT_DIR, f"treasure_qr_{url.split('/')[-1][:20]}.3mf")
    
    # Generate based on file extension
    if output_file.endswith('.stl'):
        create_3d_qr_code_combined(url, output_file)
        print(f"\n✓ Single STL created: {output_file}")
        print("  Use 'Change filament at layer' at Z=3mm for two colors")
    else:
        if not output_file.endswith('.3mf'):
            output_file += '.3mf'
        create_3d_qr_code_multicolor(url, output_file)
        print(f"\n✓ Multi-color 3MF created: {output_file}")
        print("  Open in Bambu Studio - colors pre-assigned!")
