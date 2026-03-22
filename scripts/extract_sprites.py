#!/usr/bin/env python3
"""Extract sprite-like components from a spritesheet."""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass
class Component:
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    area: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract connected sprite components.")
    parser.add_argument(
        "--job-dir",
        default="jobs/demo_work",
        help="Job directory containing input/ and extract/ subdirectories.",
    )
    parser.add_argument(
        "--input",
        default="",
        help="Input PNG with transparency.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory for crops and metadata.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=8,
        help="Alpha threshold (0-255) to treat pixels as foreground.",
    )
    parser.add_argument(
        "--segmentation-mode",
        choices=("auto", "alpha", "checker"),
        default="auto",
        help="Foreground segmentation mode.",
    )
    parser.add_argument(
        "--bg-gray-low",
        type=int,
        default=185,
        help="Checker mode: grayscale lower bound.",
    )
    parser.add_argument(
        "--bg-gray-high",
        type=int,
        default=252,
        help="Checker mode: grayscale upper bound.",
    )
    parser.add_argument(
        "--bg-chroma-tol",
        type=int,
        default=12,
        help="Checker mode: max RGB channel spread for grayscale background.",
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=20,
        help="Ignore components smaller than this pixel area.",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=2,
        help="Extra pixels around each extracted component.",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=0,
        help="Contact sheet column count. 0 means auto.",
    )
    parser.add_argument(
        "--merge-floating-symbols",
        dest="merge_floating_symbols",
        action="store_true",
        help="Merge detached tiny symbols (e.g. '?' or 'z') into nearby character components.",
    )
    parser.add_argument(
        "--no-merge-floating-symbols",
        dest="merge_floating_symbols",
        action="store_false",
        help="Disable detached symbol merging.",
    )
    parser.set_defaults(merge_floating_symbols=True)
    return parser.parse_args()


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def find_components_from_mask(mask: bytearray, width: int, height: int, min_area: int) -> list[Component]:
    visited = bytearray(width * height)
    components: list[Component] = []

    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if visited[idx]:
                continue
            if not mask[idx]:
                visited[idx] = 1
                continue

            queue: deque[tuple[int, int]] = deque()
            queue.append((x, y))
            visited[idx] = 1

            min_x = max_x = x
            min_y = max_y = y
            area = 0

            while queue:
                cx, cy = queue.popleft()
                area += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy

                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    nidx = ny * width + nx
                    if visited[nidx]:
                        continue
                    visited[nidx] = 1
                    if mask[nidx]:
                        queue.append((nx, ny))

            if area >= min_area:
                components.append(
                    Component(
                        min_x=min_x,
                        min_y=min_y,
                        max_x=max_x,
                        max_y=max_y,
                        area=area,
                    )
                )

    components.sort(key=lambda c: (c.min_y, c.min_x))
    return components


def component_width(component: Component) -> int:
    return component.max_x - component.min_x + 1


def component_height(component: Component) -> int:
    return component.max_y - component.min_y + 1


def bbox_gap(a: Component, b: Component) -> int:
    dx = max(0, max(a.min_x - b.max_x - 1, b.min_x - a.max_x - 1))
    dy = max(0, max(a.min_y - b.max_y - 1, b.min_y - a.max_y - 1))
    return dx + dy


def find_floating_symbol_target(
    source: Component,
    source_index: int,
    components: list[Component],
    max_gap: int,
) -> int | None:
    source_w = component_width(source)
    source_h = component_height(source)
    if source.area < 60 or source.area > 900:
        return None
    if source_w < 8 or source_w > 40:
        return None
    if source_h < 12 or source_h > 60:
        return None

    source_center_x = (source.min_x + source.max_x) / 2.0
    source_center_y = (source.min_y + source.max_y) / 2.0

    best_index: int | None = None
    best_gap = max_gap + 1
    best_area = -1

    for idx, target in enumerate(components):
        if idx == source_index:
            continue
        target_w = component_width(target)
        target_h = component_height(target)
        if target.area < 4000:
            continue
        if target_w < 80 or target_h < 80:
            continue
        if source.area >= target.area:
            continue

        # Floating marks in this spritesheet style typically sit at the upper-right
        # side of the character body, so keep matching conservative.
        if source_center_x < (target.min_x + target_w * 0.45):
            continue
        if source_center_x > (target.max_x + target_w * 0.45):
            continue
        if source_center_y > (target.min_y + target_h * 0.35):
            continue
        if source.max_y > (target.min_y + target_h * 0.5):
            continue

        gap = bbox_gap(source, target)
        if gap > max_gap:
            continue
        if gap < best_gap or (gap == best_gap and target.area > best_area):
            best_gap = gap
            best_area = target.area
            best_index = idx

    return best_index


def merge_floating_symbol_components(components: list[Component], max_gap: int = 24) -> tuple[list[Component], int]:
    if not components:
        return [], 0

    targets: list[int | None] = [None] * len(components)
    attachments: dict[int, list[int]] = {}

    for idx, comp in enumerate(components):
        target_index = find_floating_symbol_target(
            source=comp,
            source_index=idx,
            components=components,
            max_gap=max_gap,
        )
        if target_index is None:
            continue
        targets[idx] = target_index
        attachments.setdefault(target_index, []).append(idx)

    merged_components: list[Component] = []
    merged_count = 0

    for idx, base in enumerate(components):
        if targets[idx] is not None:
            continue

        merged_min_x = base.min_x
        merged_min_y = base.min_y
        merged_max_x = base.max_x
        merged_max_y = base.max_y
        merged_area = base.area

        for source_idx in attachments.get(idx, []):
            source = components[source_idx]
            merged_min_x = min(merged_min_x, source.min_x)
            merged_min_y = min(merged_min_y, source.min_y)
            merged_max_x = max(merged_max_x, source.max_x)
            merged_max_y = max(merged_max_y, source.max_y)
            merged_area += source.area
            merged_count += 1

        merged_components.append(
            Component(
                min_x=merged_min_x,
                min_y=merged_min_y,
                max_x=merged_max_x,
                max_y=merged_max_y,
                area=merged_area,
            )
        )

    merged_components.sort(key=lambda c: (c.min_y, c.min_x))
    return merged_components, merged_count


def is_checker_background_pixel(
    r: int,
    g: int,
    b: int,
    gray_low: int,
    gray_high: int,
    chroma_tol: int,
) -> bool:
    spread = max(r, g, b) - min(r, g, b)
    if spread > chroma_tol:
        return False
    avg = (r + g + b) // 3
    return gray_low <= avg <= gray_high


def build_foreground_mask(
    image: Image.Image,
    segmentation_mode: str,
    alpha_threshold: int,
    bg_gray_low: int,
    bg_gray_high: int,
    bg_chroma_tol: int,
) -> tuple[bytearray, str]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    alpha = rgba.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()

    mode = segmentation_mode
    if mode == "auto":
        mode = "alpha" if alpha_min < alpha_max or alpha_min < 255 else "checker"

    if mode == "alpha":
        alpha_data = list(alpha.getdata())
        mask = bytearray(1 if value > alpha_threshold else 0 for value in alpha_data)
        return mask, mode

    rgb = rgba.convert("RGB")
    rgb_px = rgb.load()
    candidate_bg = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            r, g, b = rgb_px[x, y]
            if is_checker_background_pixel(
                r=r,
                g=g,
                b=b,
                gray_low=bg_gray_low,
                gray_high=bg_gray_high,
                chroma_tol=bg_chroma_tol,
            ):
                candidate_bg[idx] = 1

    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def push_if_candidate(px: int, py: int) -> None:
        index = py * width + px
        if candidate_bg[index] and not background[index]:
            background[index] = 1
            queue.append((px, py))

    for x in range(width):
        push_if_candidate(x, 0)
        push_if_candidate(x, height - 1)
    for y in range(height):
        push_if_candidate(0, y)
        push_if_candidate(width - 1, y)

    while queue:
        cx, cy = queue.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            nidx = ny * width + nx
            if background[nidx] or not candidate_bg[nidx]:
                continue
            background[nidx] = 1
            queue.append((nx, ny))

    mask = bytearray(1 if not background[i] else 0 for i in range(width * height))
    return mask, mode


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def discover_input_path(job_dir: Path | None, input_arg: str) -> Path:
    if input_arg:
        return Path(input_arg)
    if job_dir is None:
        raise ValueError("Missing input path. Provide --input or --job-dir.")

    candidates = [
        job_dir / "input" / "source.png",
        job_dir / "input" / "work.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    png_files = sorted((job_dir / "input").glob("*.png"))
    if png_files:
        return png_files[0]
    raise FileNotFoundError(f"No PNG found under {job_dir / 'input'}")


def resolve_out_dir(job_dir: Path | None, out_dir_arg: str) -> Path:
    if out_dir_arg:
        return Path(out_dir_arg)
    if job_dir is not None:
        return job_dir / "extract"
    raise ValueError("Missing output directory. Provide --out-dir or --job-dir.")


def draw_checkerboard(image: Image.Image, block: int = 16) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    c1 = (236, 236, 236, 255)
    c2 = (214, 214, 214, 255)
    for y in range(0, height, block):
        for x in range(0, width, block):
            color = c1 if ((x // block) + (y // block)) % 2 == 0 else c2
            draw.rectangle((x, y, x + block - 1, y + block - 1), fill=color)


def create_contact_sheet(crops: list[dict], crops_dir: Path, output_path: Path, columns: int) -> None:
    if not crops:
        return

    if columns <= 0:
        columns = max(1, min(8, int(math.ceil(math.sqrt(len(crops))))))

    max_w = max(item["width"] for item in crops)
    max_h = max(item["height"] for item in crops)
    cell_w = max_w + 24
    cell_h = max_h + 42
    gap = 10
    rows = int(math.ceil(len(crops) / columns))
    sheet_w = gap + columns * (cell_w + gap)
    sheet_h = gap + rows * (cell_h + gap)

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    draw_checkerboard(sheet, block=16)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, item in enumerate(crops):
        row = index // columns
        col = index % columns
        cell_x = gap + col * (cell_w + gap)
        cell_y = gap + row * (cell_h + gap)

        crop_path = crops_dir / item["file_name"]
        with Image.open(crop_path) as crop:
            crop = crop.convert("RGBA")
            paste_x = cell_x + (cell_w - crop.width) // 2
            paste_y = cell_y + 8
            sheet.alpha_composite(crop, (paste_x, paste_y))

        label = f'#{item["id"]:03d}  {item["width"]}x{item["height"]}'
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        text_x = cell_x + (cell_w - text_w) // 2
        text_y = cell_y + cell_h - text_h - 8
        draw.rectangle(
            (text_x - 4, text_y - 2, text_x + text_w + 4, text_y + text_h + 2),
            fill=(255, 255, 255, 220),
        )
        draw.text((text_x, text_y), label, fill=(32, 32, 32, 255), font=font)

    ensure_dir(output_path.parent)
    sheet.save(output_path)


def create_bbox_preview(source: Image.Image, items: list[dict], output_path: Path) -> None:
    preview = source.convert("RGBA")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default()

    for item in items:
        x0, y0, x1, y1 = item["raw_bbox"]
        draw.rectangle((x0, y0, x1, y1), outline=(255, 67, 67, 255), width=1)
        label = str(item["id"])
        label_bbox = draw.textbbox((0, 0), label, font=font)
        label_h = label_bbox[3] - label_bbox[1]
        text_y = clamp(y0 - label_h - 2, 0, preview.height - label_h - 1)
        draw.rectangle((x0, text_y, x0 + 14, text_y + label_h + 2), fill=(255, 255, 255, 220))
        draw.text((x0 + 1, text_y + 1), label, fill=(255, 67, 67, 255), font=font)

    ensure_dir(output_path.parent)
    preview.save(output_path)


def main() -> None:
    args = parse_args()
    job_dir = Path(args.job_dir) if args.job_dir else None
    input_path = discover_input_path(job_dir=job_dir, input_arg=args.input)
    out_dir = resolve_out_dir(job_dir=job_dir, out_dir_arg=args.out_dir)
    crops_dir = out_dir / "crops"
    metadata_path = out_dir / "objects.json"
    contact_sheet_path = out_dir / "contact_sheet.png"
    bbox_preview_path = out_dir / "bbox_preview.png"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with Image.open(input_path) as im:
        image = im.convert("RGBA")

    width, height = image.size
    alpha_threshold = clamp(args.alpha_threshold, 0, 255)
    bg_gray_low = clamp(args.bg_gray_low, 0, 255)
    bg_gray_high = clamp(args.bg_gray_high, 0, 255)
    bg_chroma_tol = clamp(args.bg_chroma_tol, 0, 255)
    if bg_gray_low > bg_gray_high:
        bg_gray_low, bg_gray_high = bg_gray_high, bg_gray_low

    mask, mode_used = build_foreground_mask(
        image=image,
        segmentation_mode=args.segmentation_mode,
        alpha_threshold=alpha_threshold,
        bg_gray_low=bg_gray_low,
        bg_gray_high=bg_gray_high,
        bg_chroma_tol=bg_chroma_tol,
    )
    components = find_components_from_mask(
        mask=mask,
        width=width,
        height=height,
        min_area=max(1, args.min_area),
    )
    merged_floating_symbol_count = 0
    if args.merge_floating_symbols:
        components, merged_floating_symbol_count = merge_floating_symbol_components(components=components)

    extracted_image = image.copy()
    out_alpha = Image.new("L", (width, height), 0)
    out_alpha.putdata([255 if value else 0 for value in mask])
    extracted_image.putalpha(out_alpha)

    ensure_dir(crops_dir)

    items: list[dict] = []
    for idx, comp in enumerate(components, start=1):
        x0 = clamp(comp.min_x - args.padding, 0, width - 1)
        y0 = clamp(comp.min_y - args.padding, 0, height - 1)
        x1 = clamp(comp.max_x + args.padding, 0, width - 1)
        y1 = clamp(comp.max_y + args.padding, 0, height - 1)

        crop = extracted_image.crop((x0, y0, x1 + 1, y1 + 1))
        file_name = f"sprite_{idx:03d}.png"
        crop.save(crops_dir / file_name)

        items.append(
            {
                "id": idx,
                "file_name": file_name,
                "file": f"crops/{file_name}",
                "raw_bbox": [comp.min_x, comp.min_y, comp.max_x, comp.max_y],
                "bbox": [x0, y0, x1, y1],
                "width": x1 - x0 + 1,
                "height": y1 - y0 + 1,
                "area": comp.area,
            }
        )

    payload = {
        "job_dir": str(job_dir) if job_dir is not None else "",
        "source": str(input_path),
        "image_width": width,
        "image_height": height,
        "segmentation_mode_requested": args.segmentation_mode,
        "segmentation_mode_used": mode_used,
        "alpha_threshold": alpha_threshold,
        "bg_gray_low": bg_gray_low,
        "bg_gray_high": bg_gray_high,
        "bg_chroma_tol": bg_chroma_tol,
        "min_area": max(1, args.min_area),
        "padding": args.padding,
        "merge_floating_symbols": bool(args.merge_floating_symbols),
        "merged_floating_symbol_count": merged_floating_symbol_count,
        "count": len(items),
        "objects": items,
    }

    ensure_dir(out_dir)
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    create_contact_sheet(items, crops_dir=crops_dir, output_path=contact_sheet_path, columns=args.columns)
    create_bbox_preview(extracted_image, items, output_path=bbox_preview_path)

    print(f"Extracted {len(items)} components")
    print(f"- segmentation mode: {mode_used}")
    print(f"- merged floating symbols: {merged_floating_symbol_count}")
    print(f"- crops: {crops_dir}")
    print(f"- metadata: {metadata_path}")
    print(f"- contact sheet: {contact_sheet_path}")
    print(f"- bbox preview: {bbox_preview_path}")


if __name__ == "__main__":
    main()
