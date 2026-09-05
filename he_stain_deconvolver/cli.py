"""Command-line interface for H&E / H-DAB color deconvolution."""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .stains import STAIN_VECTORS, build_stain_matrix
from .deconvolution import (
    white_balance,
    deconvolve,
    reconstruct_stain_channel,
    compute_stain_statistics,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def parse_vector(text):
    """Parse a 'R,G,B' string into a 3-tuple of floats."""
    parts = text.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Expected 3 comma-separated numbers, e.g. 0.65,0.70,0.29 (got '{text}')"
        )
    try:
        return tuple(float(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid number in '{text}': {exc}")


def load_image(path):
    return np.array(Image.open(path).convert("RGB"))


def save_image(array, path):
    Image.fromarray(array.astype(np.uint8)).save(path)


def resolve_stain_setup(args):
    if args.custom_vectors:
        matrix, names = build_stain_matrix(args.custom_vectors)
        if args.stain_names:
            if len(args.stain_names) > len(names):
                raise ValueError("Too many --stain-names for the given --custom-vectors.")
            for i, custom_name in enumerate(args.stain_names):
                names[i] = custom_name
    else:
        preset = STAIN_VECTORS[args.stain_type]
        matrix, names = build_stain_matrix(preset)
    return matrix, names


def find_images(input_path):
    p = Path(input_path)
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)
    return [p]


def process_image(path, out_dir, matrix, names, mode, threshold, white_ref):
    image = load_image(path)
    corrected = white_balance(image, white_ref)
    concentrations = deconvolve(corrected, matrix)
    stats = compute_stain_statistics(concentrations, names, threshold)

    stem = Path(path).stem
    for i, name in enumerate(names):
        out_image = reconstruct_stain_channel(concentrations, matrix, i, mode=mode)
        save_image(out_image, Path(out_dir) / f"{stem}_{name}.png")

    return stats


def build_parser():
    parser = argparse.ArgumentParser(
        prog="he-stain-deconvolver",
        description=(
            "Separate hematoxylin/eosin or H-DAB stain contributions in RGB "
            "histology images via Ruifrok & Johnston (2001) color deconvolution."
        ),
    )
    parser.add_argument("input", help="Input image file, or a directory for batch processing")
    parser.add_argument("-o", "--output", default="deconv_output", help="Output directory")
    parser.add_argument(
        "--stain-type",
        choices=sorted(STAIN_VECTORS.keys()),
        default="HE",
        help="Built-in reference stain vectors to use (default: HE)",
    )
    parser.add_argument(
        "--custom-vectors",
        nargs="+",
        type=parse_vector,
        metavar="R,G,B",
        help="Override the preset with 2 or 3 custom stain OD vectors, e.g. "
        "--custom-vectors 0.65,0.70,0.29 0.07,0.99,0.11",
    )
    parser.add_argument(
        "--stain-names",
        nargs="+",
        help="Names for --custom-vectors, in matching order (default: stain1, stain2, ...)",
    )
    parser.add_argument(
        "--mode",
        choices=["pseudocolor", "grayscale"],
        default="pseudocolor",
        help="Rendering mode for separated stain channels (default: pseudocolor)",
    )
    parser.add_argument(
        "--white-ref",
        type=parse_vector,
        default=None,
        metavar="R,G,B",
        help="Background white reference for white-balance correction, e.g. 240,240,240 "
        "(default: no correction, i.e. assume the slide background is already white)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.15,
        help="Optical-density threshold for the percent-positive-area statistic (default: 0.15)",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        matrix, names = resolve_stain_setup(args)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    images = find_images(args.input)
    if not images:
        print(f"No images found at '{args.input}'.", file=sys.stderr)
        return 1

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    processed_count = 0
    for image_path in images:
        if not image_path.exists():
            print(f"Skipping '{image_path}': file not found.", file=sys.stderr)
            continue
        try:
            stats = process_image(
                image_path, out_dir, matrix, names, args.mode, args.threshold, args.white_ref
            )
        except Exception as exc:
            print(f"Skipping '{image_path}': {exc}", file=sys.stderr)
            continue

        processed_count += 1
        print(f"{image_path.name}:")
        for name, s in stats.items():
            print(
                f"  {name}: mean_OD={s['mean_od']:.4f}  "
                f"percent_positive_area={s['percent_positive_area']:.2f}%"
            )
        for name, s in stats.items():
            summary_rows.append(
                [image_path.name, name, s["mean_od"], s["percent_positive_area"], s["max_od"], s["min_od"]]
            )

    if processed_count == 0:
        print("No images were successfully processed.", file=sys.stderr)
        return 1

    summary_path = out_dir / "stain_statistics.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "stain", "mean_od", "percent_positive_area", "max_od", "min_od"])
        writer.writerows(summary_rows)

    print(f"\nWrote separated stain images and '{summary_path}' to '{out_dir}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
