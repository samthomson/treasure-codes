# Treasure Codes

Multi-color **3MF** QR plates for **Bambu Studio + AMS** (green base, white QR and label text).

## Setup

```bash
pip install -r requirements.txt
```

Uses **CadQuery** for rounded corners and embossed text.

## One URL — `generate_3d_qr.py`

Writes `output/treasure_qr_<hash>.3mf` unless you pass `-o`.

```bash
python generate_3d_qr.py "https://treasures.to/naddr1qfjunkaaaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqujunkaaa"
python generate_3d_qr.py "https://treasures.to/naddr1qfjunkbbbqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqujunkbbb" -o ./out/plate.3mf
python generate_3d_qr.py "https://treasures.to/naddr1qfjunkcccqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqujunkccc" -s large --style inlay -o ./out/inlay.3mf
```

**`-s`**: `small` (40mm) · `medium` (50, default) · `large` · `xlarge` · or a number in mm.  
**`--style`**: `raised` (default) · `inlay`.  
More options: `python generate_3d_qr.py --help`.

## Batch — `generate_all.py`

Same generator as above, but **only** via a text file: **one URL per line** (lines starting with `#` are comments). Outputs `qr_01.3mf`, `qr_02.3mf`, … into `output/` unless you pass `-d`.

Same shape as `urls_example.text` in this repo (junk `naddr` placeholders — swap for real links).

```bash
cp urls_example.text urls.txt
# edit urls.txt …
python generate_all.py urls.txt
python generate_all.py urls.txt -d ./out -s medium --style raised
```

`python generate_all.py --help`

## Print

Open the `.3mf` in Bambu Studio, map green / white to AMS slots, slice, print.

## Layout

| File | Role |
|------|------|
| `generate_3d_qr.py` | Main: one URL → one `.3mf` |
| `generate_all.py` | Batch: `python generate_all.py urls.txt` |
| `urls_example.text` | Example list (junk `naddr` placeholders); copy to `urls.txt` |

Generated files go in `output/` (gitignored). Keep your real list in `urls.txt` (gitignored).

## Tuning

Change geometry defaults in `generate_3d_qr.py`; for width only, use **`-s`**.
