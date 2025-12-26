#!/usr/bin/env python3
"""
Generate 3D printable QR codes with embossed text for Bambu printers.
Multi-color: Green base with white QR code squares.
"""

import qrcode
from PIL import Image
import numpy as np
try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False
    print("Warning: cadquery not available. Install with: pip install cadquery")

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
    # Black (0) becomes 1 (QR square), white (255) becomes 0
    binary = (img_array < 128).astype(int)
    return binary

def create_3d_qr_code(url, base_file, qr_pattern_file, base_height=2, qr_height=1, text_height=1.5):
    """
    Create 3D printable QR code with multi-color support.
    Generates two STL files:
    - base_file: Green base plate with text
    - qr_pattern_file: White QR code squares to place on top
    
    Args:
        url: The URL to encode in the QR code
        base_file: Output STL file for green base
        qr_pattern_file: Output STL file for white QR squares
        base_height: Height of the base plate (mm)
        qr_height: Height of QR code squares (mm)
        text_height: Height of embossed text (mm)
    """
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery is required. Install with: pip install cadquery")
    
    # Generate QR code
    qr_img = generate_qr_code(url, size=200)
    qr_array = qr_to_array(qr_img)
    
    # Dimensions
    qr_size_mm = 50  # QR code size in mm
    pixel_size = qr_size_mm / qr_array.shape[0]
    text_area_height = 12  # Space for text above QR code
    margin = 5
    total_height = text_area_height + qr_size_mm + 2 * margin
    total_width = qr_size_mm + 2 * margin
    
    # ===== CREATE BASE (GREEN) =====
    base = cq.Workplane("XY").box(total_width, total_height, base_height)
    
    # Add text "https://treasures.to" (embossed on green base)
    text_y = total_height/2 - text_area_height/2 + 2
    text_size = 2.5  # mm
    
    try:
        # Try to use cadquery's text function
        text_obj = cq.Workplane("XY").workplane(offset=base_height/2).center(0, text_y).text(
            "https://treasures.to", 
            text_size, 
            text_height,
            font="Arial",
            kind="bold"
        )
        base = base.union(text_obj)
    except:
        # Fallback: create simple raised platform for text
        print("  Note: Using simplified text representation")
        text_platform = cq.Workplane("XY").box(
            qr_size_mm * 0.9, text_area_height - 4, text_height
        ).translate((0, text_y, base_height/2 + text_height/2))
        base = base.union(text_platform)
    
    # Export base to STL
    cq.exporters.export(base, base_file)
    print(f"✓ Created base (green): {base_file}")
    
    # ===== CREATE QR PATTERN (WHITE SQUARES) =====
    # Position QR code below text area
    qr_offset_y = -text_area_height / 2
    
    # Create a union of all white squares
    qr_squares = None
    
    for i in range(qr_array.shape[0]):
        for j in range(qr_array.shape[1]):
            if qr_array[i, j] == 1:  # Black pixel = white square on top
                x = (j - qr_array.shape[1]/2) * pixel_size
                y = (qr_array.shape[0]/2 - i) * pixel_size + qr_offset_y
                
                # Create raised square
                square = cq.Workplane("XY").box(
                    pixel_size * 0.95, pixel_size * 0.95, qr_height
                ).translate((x, y, qr_height/2))
                
                if qr_squares is None:
                    qr_squares = square
                else:
                    qr_squares = qr_squares.union(square)
    
    if qr_squares is None:
        # Create empty object if no squares
        qr_squares = cq.Workplane("XY").box(1, 1, 0.1)
    
    # Export QR pattern to STL
    cq.exporters.export(qr_squares, qr_pattern_file)
    print(f"✓ Created QR pattern (white): {qr_pattern_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python generate_3d_qr.py <url> [base_file.stl] [qr_pattern_file.stl]")
        sys.exit(1)
    
    url = sys.argv[1]
    base_file = sys.argv[2] if len(sys.argv) > 2 else f"base_{url.split('/')[-1][:20]}.stl"
    qr_pattern_file = sys.argv[3] if len(sys.argv) > 3 else f"qr_pattern_{url.split('/')[-1][:20]}.stl"
    
    try:
        create_3d_qr_code(url, base_file, qr_pattern_file)
        print(f"\n✓ Success! Files ready for Bambu printer:")
        print(f"  Base (green): {base_file}")
        print(f"  QR pattern (white): {qr_pattern_file}")
        print(f"  URL encoded: {url}")
        print(f"  Text above: https://treasures.to")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

