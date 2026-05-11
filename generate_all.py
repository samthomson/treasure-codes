#!/usr/bin/env python3
"""
Batch wrapper over generate_3d_qr.generate(): reads a URL list file → qr_01.3mf, …
"""

import argparse
import os

from generate_3d_qr import OUTPUT_DIR, generate as generate_qr_plate
from generate_container import BODY_HEIGHT_MODES, DEFAULT_TEMPLATE, generate_container


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
        description="Batch-generate 3MFs from a URL list file (QR plates or containers/lids).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "url_file",
        help="Text file with one URL per line (# starts a comment)",
    )
    parser.add_argument(
        "--mode",
        choices=["qr_plate", "container", "container_lid", "container_full"],
        default="qr_plate",
        help="What to generate for each URL",
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
        help="QR size preset/mm for qr_plate, or QR size mm for container_lid/container_full",
    )
    parser.add_argument(
        "--style",
        choices=["raised", "inlay"],
        default="raised",
        help="qr_plate mode only: raised=QR on top; inlay=flat surface",
    )
    parser.add_argument(
        "-v",
        "--variant",
        choices=["large", "small"],
        default="large",
        help="container/container_lid modes only: container size variant",
    )
    parser.add_argument(
        "-t",
        "--template",
        default=DEFAULT_TEMPLATE,
        help="container/container_lid modes only: template 3MF path",
    )
    parser.add_argument(
        "--body-height",
        choices=list(BODY_HEIGHT_MODES),
        default="medium",
        help="container/container_full modes only: bottom body height (top clasp unchanged)",
    )
    parser.add_argument(
        "--container-size",
        choices=["small", "medium", "large"],
        default=None,
        help="Alias for --body-height in container/container_full modes",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.url_file):
        parser.error(f"Not a file: {args.url_file!r}")

    urls = load_urls_from_file(args.url_file)
    if not urls:
        parser.error(f"No URLs found in {args.url_file!r} (add one URL per line)")

    os.makedirs(args.output_dir, exist_ok=True)

    if args.mode == "qr_plate":
        output_prefix = "qr"
    elif args.mode == "container":
        output_prefix = "container"
    elif args.mode == "container_full":
        output_prefix = "container_full"
    else:
        output_prefix = "container_lid"

    container_qr_size = None
    if args.mode in ("container_lid", "container_full"):
        if args.size == "medium":
            container_qr_size = None
        else:
            try:
                container_qr_size = float(args.size)
            except ValueError:
                parser.error(
                    "--size must be numeric (mm) for container_lid/container_full mode; "
                    "use default for auto-fit."
                )

    body_height = args.container_size or args.body_height

    for i, url in enumerate(urls, 1):
        output_file = os.path.join(args.output_dir, f"{output_prefix}_{i:02d}.3mf")
        print(f"\n[{i}/{len(urls)}] Generating…")
        print(f"  URL: {url[:72]}{'…' if len(url) > 72 else ''}")
        try:
            if args.mode == "qr_plate":
                generate_qr_plate(url, output_file, args.size, args.style)
            else:
                generate_container(
                    url,
                    output_file,
                    template=args.template,
                    variant=args.variant,
                    qr_size=container_qr_size,
                    lids_only=args.mode == "container_lid",
                    base_only=args.mode == "container",
                    body_height=body_height,
                )
            print(f"  ✓ Saved: {output_file}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Done. {len(urls)} file(s) in {args.output_dir!r}")


if __name__ == "__main__":
    main()
