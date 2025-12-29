#!/usr/bin/env python3
"""
Generate 3D QR codes for all treasure URLs.
Outputs multi-color 3MF files ready for Bambu AMS printing.
"""

from generate_3d_qr import create_3d_qr_code_multicolor
import os

# Seed URLs from README
URLS = [
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsq8nfde6xzcm594ekzmrddahz6umrv9kxcmms95erqwfnvfskzwqkm2c9g",
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsq8r8v4hx2unpdskk7unpdenk2ttzv9ehxtfjxqunxcnpvyuqgl6ww4",
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsqgmfde6x2un9wd6x2epdd4shymm0dckkkctwvashymm095erqwfnvfskzwqayajqs",
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsqgm90pcx2unfv4hxxety943k7enxv4jj6arpwfekjetj95erqwfnvfskzwqwdur7t",
]

OUTPUT_DIR = "output"


def generate_all():
    """Generate 3MF files for all URLs."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for i, url in enumerate(URLS, 1):
        output_file = os.path.join(OUTPUT_DIR, f"treasure_{i:02d}.3mf")
        
        print(f"\n[{i}/{len(URLS)}] Generating QR code for treasure {i}...")
        print(f"  URL: {url[:60]}...")
        
        try:
            create_3d_qr_code_multicolor(url, output_file)
            print(f"  ✓ Saved: {output_file}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"✓ Generated {len(URLS)} multi-color 3MF files in '{OUTPUT_DIR}/'")
    print(f"\n  In Bambu Studio:")
    print(f"  1. Open any .3mf file")
    print(f"  2. Two parts with colors pre-assigned (green base, white QR)")
    print(f"  3. Map to your AMS filaments and print!")


if __name__ == "__main__":
    generate_all()
