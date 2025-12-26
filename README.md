# Treasure Codes - 3D Printable QR Codes

Generate custom 3D printable QR codes for the treasures app. Each QR code is designed for multi-color printing on Bambu printers with green base and white QR code squares.

## Seed URLs

```
https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsq8nfde6xzcm594ekzmrddahz6umrv9kxcmms95erqwfnvfskzwqkm2c9g
```

```
https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsq8r8v4hx2unpdskk7unpdenk2ttzv9ehxtfjxqunxcnpvyuqgl6ww4
```

```
https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsqgmfde6x2un9wd6x2epdd4shymm0dckkkctwvashymm095erqwfnvfskzwqayajqs
```

```
https://treasures.to/naddr1qvzqqqyj3spzqgynh25xy8zmy40g7n7zcm7lcyxc54vc5f23wejwl2agvpe47ypsqy28wumn8ghj7un9d3shjtnyv9kh2uewd9hsqgm90pcx2unfv4hxxety943k7enxv4jj6arpwfekjetj95erqwfnvfskzwqwdur7t
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Generate all QR codes:
   ```bash
   python generate_all.py
   ```

This creates STL files in the `stl_files/` directory.

## Multi-Color Printing in Bambu Studio

Each QR code generates two STL files:
- `treasure_XX_base.stl` - Green base with "https://treasures.to" text
- `treasure_XX_qr_pattern.stl` - White QR code squares

### Method 1: Using Modifier Meshes (Recommended)

1. Import the base file: `File → Import → STL` (select `treasure_XX_base.stl`)
2. Import the QR pattern as a modifier:
   - `File → Import → STL` (select `treasure_XX_qr_pattern.stl`)
   - In the object list, right-click the QR pattern → `Convert to modifier mesh`
   - Select the QR pattern modifier, go to `Modifier` tab
   - Set `Type` to `Color Painting` or use `Flush into object`
   - Assign white filament to the modifier
   - Assign green filament to the base

3. Print settings:
   - Layer height: 0.2 mm
   - Infill: 20%
   - Supports: Off
   - Enable AMS for multi-color printing

### Method 2: Separate Objects

1. Import both STL files
2. Position the QR pattern on top of the base (they should align automatically)
3. Assign colors:
   - Select base object → assign green filament
   - Select QR pattern object → assign white filament
4. Ensure both objects are at the same Z=0 position

## File Structure

```
treasure-codes/
├── README.md
├── requirements.txt
├── generate_3d_qr.py
├── generate_all.py
└── stl_files/
    ├── treasure_01_base.stl
    ├── treasure_01_qr_pattern.stl
    ├── treasure_02_base.stl
    ├── treasure_02_qr_pattern.stl
    └── ...
```

## Customization

To generate a single QR code:
```bash
python generate_3d_qr.py "https://treasures.to/your-url" base.stl qr_pattern.stl
```

Adjust dimensions in `generate_3d_qr.py`:
- `qr_size_mm`: Size of QR code (default: 50mm)
- `base_height`: Base plate thickness (default: 2mm)
- `qr_height`: Height of white squares (default: 1mm)
- `text_height`: Height of embossed text (default: 1.5mm)

