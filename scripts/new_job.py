#!/usr/bin/env python3
"""Create a reusable job directory for sprite extraction/composition."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a new job folder.")
    parser.add_argument("--job", required=True, help="Job name, e.g. my_project_001")
    parser.add_argument("--source", default="", help="Optional source PNG to copy into input/source.png")
    parser.add_argument("--reference", default="", help="Optional reference image to copy into input/reference.webp")
    parser.add_argument(
        "--canvas",
        default="2400x1500",
        help="Canvas size for layout template, format WIDTHxHEIGHT.",
    )
    return parser.parse_args()


def parse_canvas_size(value: str) -> tuple[int, int]:
    lowered = value.lower().strip()
    if "x" not in lowered:
        raise ValueError("canvas must be WIDTHxHEIGHT, e.g. 2400x1500")
    width_str, height_str = lowered.split("x", 1)
    width = int(width_str)
    height = int(height_str)
    if width <= 0 or height <= 0:
        raise ValueError("canvas dimensions must be positive")
    return width, height


def write_layout_template(path: Path, canvas_w: int, canvas_h: int) -> None:
    payload = {
        "canvas": {"width": canvas_w, "height": canvas_h},
        "rows": [[], [], [], [], []],
        "notes": "Fill row IDs using extract/contact_sheet.png",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_if_present(src_str: str, dst: Path) -> None:
    if not src_str:
        return
    src = Path(src_str)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")
    shutil.copy2(src, dst)


def main() -> None:
    args = parse_args()
    canvas_w, canvas_h = parse_canvas_size(args.canvas)

    job_dir = Path("jobs") / args.job
    input_dir = job_dir / "input"
    extract_dir = job_dir / "extract"
    output_dir = job_dir / "output"
    for path in (input_dir, extract_dir, output_dir):
        path.mkdir(parents=True, exist_ok=True)

    layout_path = job_dir / "layout.json"
    if not layout_path.exists():
        write_layout_template(layout_path, canvas_w, canvas_h)

    copy_if_present(args.source, input_dir / "source.png")
    copy_if_present(args.reference, input_dir / "reference.webp")

    print(f"Job ready: {job_dir}")
    print(f"- input: {input_dir}")
    print(f"- extract: {extract_dir}")
    print(f"- output: {output_dir}")
    print(f"- layout template: {layout_path}")


if __name__ == "__main__":
    main()
