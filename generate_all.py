#!/usr/bin/env python3
"""
Batch wrapper over generate_3d_qr.generate(): reads a URL list file → qr_01.3mf, …
"""

import argparse
import os

from generate_3d_qr import OUTPUT_DIR, generate


def load_urls_from_file(path):
    urls = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def main():
    parser = argparse.ArgumentParser(
        description="Batch-generate multi-color 3MF QR plates from a URL list file (Bambu AMS).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "url_file",
        help="Text file with one URL per line (# starts a comment)",
    )
    parser.add_argument(
        "-d",
        "--output-dir",
        default=OUTPUT_DIR,
        help="Directory for generated files",
    )
    parser.add_argument(
        "-s",
        "--size",
        default="medium",
        help="Size preset or mm value (same as generate_3d_qr.py)",
    )
    parser.add_argument(
        "--style",
        choices=["raised", "inlay"],
        default="raised",
        help="raised=QR on top; inlay=flat surface",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.url_file):
        parser.error(f"Not a file: {args.url_file!r}")

    urls = load_urls_from_file(args.url_file)
    if not urls:
        parser.error(f"No URLs found in {args.url_file!r} (add one URL per line)")

    os.makedirs(args.output_dir, exist_ok=True)

    for i, url in enumerate(urls, 1):
        output_file = os.path.join(args.output_dir, f"qr_{i:02d}.3mf")
        print(f"\n[{i}/{len(urls)}] Generating…")
        print(f"  URL: {url[:72]}{'…' if len(url) > 72 else ''}")
        try:
            generate(url, output_file, args.size, args.style)
            print(f"  ✓ Saved: {output_file}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Done. {len(urls)} file(s) in {args.output_dir!r}")


if __name__ == "__main__":
    main()
