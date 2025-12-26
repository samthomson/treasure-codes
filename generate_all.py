#!/usr/bin/env python3
"""
Generate 3D QR codes for all treasure URLs.
Multi-color: Green base with white QR code squares.
"""

from generate_3d_qr import create_3d_qr_code
import os

# Seed URLs from README
urls = [
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsq8nfde6xzcm594ekzmrddahz6umrv9kxcmms95erqwfnvfskzwqkm2c9g",
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsq8r8v4hx2unpdskk7unpdenk2ttzv9ehxtfjxqunxcnpvyuqgl6ww4",
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsqgmfde6x2un9wd6x2epdd4shymm0dckkkctwvashymm095erqwfnvfskzwqayajqs",
    "https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsqgm90pcx2unfv4hxxety943k7enxv4jj6arpwfekjetj95erqwfnvfskzwqwdur7t",
]

def generate_all():
    """Generate STL files for all URLs."""
    output_dir = "stl_files"
    os.makedirs(output_dir, exist_ok=True)
    
    for i, url in enumerate(urls, 1):
        # Extract a short identifier from the URL
        url_id = url.split('/')[-1][:30]  # First 30 chars of the naddr
        base_file = os.path.join(output_dir, f"treasure_{i:02d}_base.stl")
        qr_pattern_file = os.path.join(output_dir, f"treasure_{i:02d}_qr_pattern.stl")
        
        print(f"\n[{i}/{len(urls)}] Generating QR code for treasure {i}...")
        print(f"  URL: {url[:60]}...")
        
        try:
            create_3d_qr_code(url, base_file, qr_pattern_file)
            print(f"  ✓ Saved: {base_file}")
            print(f"  ✓ Saved: {qr_pattern_file}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"✓ Generated {len(urls)} QR code sets ({len(urls)*2} STL files) in '{output_dir}/'")
    print(f"  Each set includes:")
    print(f"    - Base (green): treasure_XX_base.stl")
    print(f"    - QR pattern (white): treasure_XX_qr_pattern.stl")
    print(f"\n  Ready to import into Bambu Studio for multi-color printing!")

if __name__ == "__main__":
    generate_all()

