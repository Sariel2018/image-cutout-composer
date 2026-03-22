#!/usr/bin/env python3
"""Compose selected sprite crops into a multi-row final image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose sprites with a row-based layout.")
    parser.add_argument(
        "--job-dir",
        default="jobs/demo_work",
        help="Job directory containing extract/, layout.json and output/.",
    )
    parser.add_argument("--objects", default="", help="Metadata JSON from extraction.")
    parser.add_argument("--layout", default="", help="Layout JSON with rows of IDs.")
    parser.add_argument("--crops-dir", default="", help="Directory containing extracted PNG crops.")
    parser.add_argument("--reference", default="", help="Reference image used to guide compact layout.")
    parser.add_argument("--output", default="", help="Output PNG path.")
    parser.add_argument("--output-webp", default="", help="Output WEBP path.")
    parser.add_argument("--report", default="", help="Placement report JSON path.")
    parser.add_argument(
        "--style",
        choices=("strip", "compact"),
        default="strip",
        help="Layout style: strip (legacy yellow strips) or compact (transparent + tighter spacing).",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path, Path, Path]:
    job_dir = Path(args.job_dir) if args.job_dir else None

    objects_path = Path(args.objects) if args.objects else (
        job_dir / "extract" / "objects.json" if job_dir else Path("objects.json")
    )
    layout_path = Path(args.layout) if args.layout else (
        job_dir / "layout.json" if job_dir else Path("layout.json")
    )
    crops_dir = Path(args.crops_dir) if args.crops_dir else (
        job_dir / "extract" / "crops" if job_dir else Path("crops")
    )
    output_png = Path(args.output) if args.output else (
        job_dir / "output" / "final.png" if job_dir else Path("final.png")
    )
    output_webp = Path(args.output_webp) if args.output_webp else (
        job_dir / "output" / "final.webp" if job_dir else Path("final.webp")
    )
    report_path = Path(args.report) if args.report else (
        job_dir / "output" / "composition.json" if job_dir else Path("composition.json")
    )

    return objects_path, layout_path, crops_dir, output_png, output_webp, report_path


def discover_reference_path(job_dir: Path | None, reference_arg: str) -> Path | None:
    if reference_arg:
        return Path(reference_arg)
    if job_dir is None:
        return None

    patterns = [
        "input/reference.webp",
        "input/reference.png",
        "input/*reference*.webp",
        "input/*reference*.png",
        "*-reference.webp",
        "*-reference.png",
        "reference.webp",
        "reference.png",
        "*reference*.webp",
        "*reference*.png",
    ]
    for pattern in patterns:
        matches = sorted(job_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def analyze_reference_layout(reference_path: Path, alpha_threshold: int = 20) -> dict | None:
    if not reference_path.exists():
        return None

    with Image.open(reference_path) as ref:
        rgba = ref.convert("RGBA")
    width, height = rgba.size
    alpha = rgba.getchannel("A")
    alpha_px = alpha.load()

    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    row_counts: list[int] = [0] * height

    for y in range(height):
        count = 0
        for x in range(width):
            if alpha_px[x, y] <= alpha_threshold:
                continue
            count += 1
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
        row_counts[y] = count

    if max_x < 0 or max_y < 0:
        return None

    row_activation_threshold = max(20, int(width * 0.02))
    row_is_active = [count > row_activation_threshold for count in row_counts]

    row_segments: list[tuple[int, int]] = []
    in_segment = False
    start = 0
    for y, active in enumerate(row_is_active):
        if active and not in_segment:
            start = y
            in_segment = True
            continue
        if not active and in_segment:
            row_segments.append((start, y - 1))
            in_segment = False
    if in_segment:
        row_segments.append((start, height - 1))

    if not row_segments:
        row_segments = [(min_y, max_y)]

    return {
        "content_bbox": (min_x, min_y, max_x, max_y),
        "row_segments": row_segments,
    }


def map_row_to_guide_segment(row_index: int, row_count: int, segment_count: int) -> int:
    if segment_count <= 1 or row_count <= 1:
        return 0
    mapped = round(row_index * (segment_count - 1) / (row_count - 1))
    return max(0, min(segment_count - 1, mapped))


def chunk_width(height: int, width: int, target_h: int) -> int:
    if height <= 0:
        return width
    return max(1, round(width * (target_h / height)))


def compose(
    objects_path: Path,
    layout_path: Path,
    crops_dir: Path,
    output_png: Path,
    output_webp: Path,
    report_path: Path,
    style: str,
    reference_path: Path | None,
) -> None:
    objects_data = load_json(objects_path)
    layout_data = load_json(layout_path)

    canvas_w = int(layout_data.get("canvas", {}).get("width", 2400))
    canvas_h = int(layout_data.get("canvas", {}).get("height", 1500))
    rows: list[list[int]] = layout_data.get("rows", [])
    if not rows:
        raise ValueError("layout rows is empty")

    object_map = {int(item["id"]): item for item in objects_data.get("objects", [])}

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    row_count = len(rows)
    if style == "compact":
        top_margin = 40
        bottom_margin = 40
        row_gap = 24 if row_count > 1 else 0
    else:
        top_margin = 60
        bottom_margin = 60
        row_gap = 48 if row_count > 1 else 0
    row_h = (canvas_h - top_margin - bottom_margin - row_gap * (row_count - 1)) // row_count
    row_h = max(120, row_h)

    reference_guide = None
    if style == "compact" and reference_path is not None:
        reference_guide = analyze_reference_layout(reference_path=reference_path)

    strip_colors = [
        (231, 210, 145, 236),
        (224, 199, 136, 230),
        (236, 214, 152, 236),
        (227, 202, 139, 232),
        (238, 218, 160, 236),
    ]

    placements: list[dict] = []
    for row_idx, row_ids in enumerate(rows):
        row_top = top_margin + row_idx * (row_h + row_gap)

        baseline = row_top + int(row_h * (0.87 if style == "strip" else 0.9))
        default_target_h = int(row_h * (0.72 if style == "strip" else 0.66))
        target_h = default_target_h
        if style == "compact" and reference_guide is not None:
            guide_segments: list[tuple[int, int]] = reference_guide["row_segments"]
            segment_idx = map_row_to_guide_segment(
                row_index=row_idx,
                row_count=row_count,
                segment_count=len(guide_segments),
            )
            seg_y0, seg_y1 = guide_segments[segment_idx]
            seg_h = max(1, seg_y1 - seg_y0 + 1)
            row_top = seg_y0
            segment_target_h = max(32, int(seg_h * 0.66))
            target_h = max(default_target_h, segment_target_h)
            baseline = seg_y1 - max(2, int(seg_h * 0.10))
            if target_h > segment_target_h:
                baseline += target_h - segment_target_h
            baseline = max(target_h + 2, min(canvas_h - 2, baseline))

        if style == "strip":
            strip_h = int(row_h * 0.58)
            strip_y = row_top + int(row_h * 0.24)
            strip_color = strip_colors[row_idx % len(strip_colors)]
            draw.rounded_rectangle(
                (32, strip_y, canvas_w - 32, strip_y + strip_h),
                radius=14,
                fill=strip_color,
            )

        if not row_ids:
            continue

        prepared_row: list[tuple[int, Image.Image]] = []
        for sprite_id in row_ids:
            if int(sprite_id) not in object_map:
                raise ValueError(f"Sprite id not found in objects.json: {sprite_id}")
            item = object_map[int(sprite_id)]
            sprite_path = crops_dir / item["file_name"]
            if not sprite_path.exists():
                raise FileNotFoundError(f"Missing crop file: {sprite_path}")

            with Image.open(sprite_path) as im:
                sprite = im.convert("RGBA")

            scale_h = target_h
            if sprite.height < 40:
                scale_h = min(target_h, sprite.height * 2)
            new_w = chunk_width(sprite.height, sprite.width, scale_h)
            resized = sprite.resize((new_w, scale_h), Image.Resampling.LANCZOS)
            prepared_row.append((int(sprite_id), resized))

        if style == "strip":
            left = 130
            right = canvas_w - 130
            if len(prepared_row) == 1:
                centers = [(left + right) // 2]
            else:
                step = (right - left) / (len(prepared_row) - 1)
                centers = [round(left + i * step) for i in range(len(prepared_row))]

            for col_idx, (sprite_id, resized) in enumerate(prepared_row):
                x = centers[col_idx] - (resized.width // 2)
                y = baseline - resized.height
                canvas.alpha_composite(resized, (x, y))

                placements.append(
                    {
                        "id": int(sprite_id),
                        "row": row_idx + 1,
                        "column": col_idx + 1,
                        "x": x,
                        "y": y,
                        "width": resized.width,
                        "height": resized.height,
                    }
                )
            continue

        if reference_guide is not None:
            guide_x0, _, guide_x1, _ = reference_guide["content_bbox"]
            guide_w = max(1, guide_x1 - guide_x0 + 1)
            left = max(16, guide_x0 + int(guide_w * 0.04))
            right = min(canvas_w - 16, guide_x1 - int(guide_w * 0.04))

            if right > left:
                if len(prepared_row) == 1:
                    centers = [(left + right) // 2]
                else:
                    step = (right - left) / (len(prepared_row) - 1)
                    centers = [round(left + i * step) for i in range(len(prepared_row))]

                # Reference-guided center spacing may clip wide sprites at canvas edges.
                # Apply a uniform downscale so all sprites stay fully visible.
                scale = 1.0
                for (_, sprite), center_x in zip(prepared_row, centers):
                    max_w_here = max(1, 2 * min(center_x, canvas_w - center_x))
                    scale = min(scale, max_w_here / max(1, sprite.width))

                # If guide requires heavy downscale, reference is likely not compatible
                # with this row; fall back to normal compact packing.
                if scale < 0.85:
                    pass
                elif scale < 1.0:
                    resized_row: list[tuple[int, Image.Image]] = []
                    for sprite_id, sprite in prepared_row:
                        new_w = max(1, round(sprite.width * scale))
                        new_h = max(1, round(sprite.height * scale))
                        resized_row.append(
                            (
                                sprite_id,
                                sprite.resize((new_w, new_h), Image.Resampling.LANCZOS),
                            )
                        )
                    prepared_row = resized_row

                if scale >= 0.85:
                    for col_idx, (sprite_id, resized) in enumerate(prepared_row):
                        x = centers[col_idx] - (resized.width // 2)
                        y = baseline - resized.height
                        canvas.alpha_composite(resized, (x, y))

                        placements.append(
                            {
                                "id": int(sprite_id),
                                "row": row_idx + 1,
                                "column": col_idx + 1,
                                "x": x,
                                "y": y,
                                "width": resized.width,
                                "height": resized.height,
                            }
                        )
                    continue

        # compact style: keep transparent background and pack each row by content width
        # instead of spreading sprites across the full canvas width.
        gap_px = 24
        min_gap_px = 8
        row_count_items = len(prepared_row)
        total_sprite_width = sum(sprite.width for _, sprite in prepared_row)
        row_width = total_sprite_width + gap_px * max(0, row_count_items - 1)

        max_row_width = canvas_w - 48
        if row_width > max_row_width and row_count_items > 1:
            fit_gap = max(min_gap_px, (max_row_width - total_sprite_width) // (row_count_items - 1))
            gap_px = fit_gap
            row_width = total_sprite_width + gap_px * (row_count_items - 1)

        # If reducing gaps is not enough, uniformly shrink the whole row to avoid clipping.
        if row_width > max_row_width and row_count_items >= 1:
            max_content_width = max(1, max_row_width - min_gap_px * max(0, row_count_items - 1))
            scale = max_content_width / max(1, total_sprite_width)
            if scale < 1.0:
                resized_row: list[tuple[int, Image.Image]] = []
                for sprite_id, sprite in prepared_row:
                    new_w = max(1, round(sprite.width * scale))
                    new_h = max(1, round(sprite.height * scale))
                    resized_row.append(
                        (
                            sprite_id,
                            sprite.resize((new_w, new_h), Image.Resampling.LANCZOS),
                        )
                    )
                prepared_row = resized_row
                total_sprite_width = sum(sprite.width for _, sprite in prepared_row)
                gap_px = min_gap_px if row_count_items > 1 else 0
                row_width = total_sprite_width + gap_px * max(0, row_count_items - 1)

        x_cursor = (canvas_w - row_width) // 2

        for col_idx, (sprite_id, resized) in enumerate(prepared_row):
            x = x_cursor
            y = baseline - resized.height
            canvas.alpha_composite(resized, (x, y))

            placements.append(
                {
                    "id": int(sprite_id),
                    "row": row_idx + 1,
                    "column": col_idx + 1,
                    "x": x,
                    "y": y,
                    "width": resized.width,
                    "height": resized.height,
                }
            )

            x_cursor += resized.width + gap_px

    ensure_parent(output_png)
    canvas.save(output_png)
    ensure_parent(output_webp)
    canvas.save(output_webp, format="WEBP", lossless=True, quality=95, method=6)

    report = {
        "canvas": {"width": canvas_w, "height": canvas_h},
        "style": style,
        "reference": str(reference_path) if reference_path else "",
        "rows": rows,
        "placements": placements,
    }
    ensure_parent(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Composed {len(placements)} sprites")
    print(f"- output png: {output_png}")
    print(f"- output webp: {output_webp}")
    print(f"- report: {report_path}")


def main() -> None:
    args = parse_args()
    objects_path, layout_path, crops_dir, output_png, output_webp, report_path = resolve_paths(args)
    job_dir = Path(args.job_dir) if args.job_dir else None
    reference_path = discover_reference_path(job_dir=job_dir, reference_arg=args.reference)
    compose(
        objects_path=objects_path,
        layout_path=layout_path,
        crops_dir=crops_dir,
        output_png=output_png,
        output_webp=output_webp,
        report_path=report_path,
        style=args.style,
        reference_path=reference_path,
    )


if __name__ == "__main__":
    main()
