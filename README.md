# Treasure Codes - 3D Printable QR Codes

Generate custom 3D printable QR codes for the treasures app. Each QR code is designed for multi-color printing on Bambu printers with AMS (green base + white QR squares).

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

```bash
pip install -r requirements.txt
```

## Usage

### Generate all QR codes (batch)

```bash
python generate_all.py
```

Creates 3MF files for all seed URLs in the `output/` directory.

### Generate a single QR code

```bash
# Multi-color 3MF (for Bambu AMS)
python generate_3d_qr.py "https://treasures.to/your-url"

# Single STL (for filament change)
python generate_3d_qr.py "https://treasures.to/your-url" output.stl
```

## Output Formats

### 3MF (recommended for Bambu AMS)
- Single file with two colored parts embedded
- Opens in Bambu Studio with colors pre-assigned
- Green base + white QR/text

### STL (for non-AMS printers)
- Single combined mesh
- Use "Change filament at layer" at Z=3mm
- Print base in green, swap to white for QR/text

## Printing in Bambu Studio

### With AMS (multi-filament)
1. Open the `.3mf` file
2. Colors should be pre-assigned (green + white)
3. Map colors to your AMS filament slots
4. Print!

### Without AMS (single filament)
1. Open the `.stl` file
2. Slice the model
3. In Preview, find layer at Z=3mm (around layer 15)
4. Right-click → Add pause/filament change
5. Print - swap filament when paused

## File Structure

```
treasure-codes/
├── README.md
├── requirements.txt
├── .gitignore
├── generate_3d_qr.py      # Main generation script
├── generate_all.py        # Batch generation for all URLs
└── output/                # Generated models (gitignored)
    ├── treasure_01.3mf
    ├── treasure_02.3mf
    └── ...
```

## Scripts Summary

| Script | Purpose |
|--------|---------|
| `generate_3d_qr.py` | Main script - generates single QR code (3MF or STL) |
| `generate_all.py` | Batch script - generates all 4 seed URL QR codes |

## Customization

Edit `generate_3d_qr.py` to adjust dimensions:
- `qr_size_mm = 70` - QR code size (mm)
- `base_height = 3` - Base plate thickness (mm)
- `qr_height = 1.5` - Height of QR squares (mm)
- `text_height = 2` - Height of embossed text (mm)
