#!/usr/bin/env python3
"""Compose a strict frame-grid spritesheet aligned to a reference sheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from PIL import Image, ImageChops, ImageFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose a strict spritesheet grid for frontend frame slicing.")
    parser.add_argument(
        "--job-dir",
        required=True,
        help="Job directory containing extract/, layout.json, optional *-reference.* and output/.",
    )
    parser.add_argument("--objects", default="", help="Path to objects.json.")
    parser.add_argument("--layout", default="", help="Path to layout.json.")
    parser.add_argument("--crops-dir", default="", help="Path to crops directory.")
    parser.add_argument("--reference", default="", help="Reference spritesheet path.")
    parser.add_argument("--frame-width", type=int, required=True, help="Frame width in pixels.")
    parser.add_argument("--frame-height", type=int, required=True, help="Frame height in pixels.")
    parser.add_argument("--output", default="", help="Output PNG path.")
    parser.add_argument("--output-webp", default="", help="Output WEBP path.")
    parser.add_argument("--report", default="", help="Output report JSON path.")
    parser.add_argument(
        "--fill-mode",
        choices=("cycle", "hold-last"),
        default="cycle",
        help="How to fill frames when selected ids are fewer than grid size.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=20,
        help="Alpha threshold for reference analysis.",
    )
    parser.add_argument(
        "--defringe-white",
        action="store_true",
        help="Try to remove white matte fringe on semi-transparent edge pixels.",
    )
    parser.add_argument(
        "--outline-size",
        type=int,
        default=0,
        help="Black outline width in pixels (0 disables outline).",
    )
    parser.add_argument(
        "--outline-alpha",
        type=int,
        default=230,
        help="Outline alpha (0-255).",
    )
    parser.add_argument(
        "--outline-threshold",
        type=int,
        default=24,
        help="Alpha threshold used to detect solid body for outline generation.",
    )
    parser.add_argument(
        "--sharpen",
        action="store_true",
        help="Apply a mild unsharp mask after resize for cleaner details.",
    )
    parser.add_argument(
        "--blacken-fringe",
        action="store_true",
        help="Force bright semi-transparent outer fringe pixels to black.",
    )
    parser.add_argument(
        "--fringe-alpha-max",
        type=int,
        default=220,
        help="Upper alpha bound for fringe blackening candidates.",
    )
    parser.add_argument(
        "--fringe-luma-min",
        type=int,
        default=130,
        help="Minimum luma for fringe blackening candidates.",
    )
    parser.add_argument(
        "--fringe-chroma-max",
        type=int,
        default=70,
        help="Maximum RGB spread for fringe blackening candidates.",
    )
    parser.add_argument(
        "--fringe-iterations",
        type=int,
        default=1,
        help="How many passes to blacken fringe.",
    )
    parser.add_argument(
        "--force-black-edge-width",
        type=int,
        default=0,
        help="Force paint the outer N-pixel alpha edge band to black (0 disables).",
    )
    parser.add_argument(
        "--force-black-edge-alpha-floor",
        type=int,
        default=0,
        help="If >0, edge pixels alpha is raised to at least this value.",
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_reference_path(job_dir: Path, explicit: str) -> Path | None:
    if explicit:
        return Path(explicit)

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


def median_or_default(values: list[float], default_value: float) -> float:
    if not values:
        return default_value
    return float(median(values))


def analyze_reference_cells(
    reference_path: Path,
    frame_w: int,
    frame_h: int,
    alpha_threshold: int,
) -> dict:
    with Image.open(reference_path) as im:
        ref = im.convert("RGBA")

    width, height = ref.size
    if width % frame_w != 0 or height % frame_h != 0:
        raise ValueError(
            f"Reference size {width}x{height} is not divisible by frame {frame_w}x{frame_h}: {reference_path}"
        )

    cols = width // frame_w
    rows = height // frame_h
    alpha = ref.getchannel("A")
    px = alpha.load()

    h_ratios: list[float] = []
    w_ratios: list[float] = []
    bottom_ratios: list[float] = []

    for row in range(rows):
        for col in range(cols):
            x0 = col * frame_w
            y0 = row * frame_h
            min_x = frame_w
            min_y = frame_h
            max_x = -1
            max_y = -1

            for y in range(frame_h):
                yy = y0 + y
                for x in range(frame_w):
                    if px[x0 + x, yy] <= alpha_threshold:
                        continue
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y

            if max_x < 0:
                continue

            obj_w = max_x - min_x + 1
            obj_h = max_y - min_y + 1
            h_ratios.append(obj_h / frame_h)
            w_ratios.append(obj_w / frame_w)
            bottom_ratios.append((max_y + 1) / frame_h)

    return {
        "cols": cols,
        "rows": rows,
        "frame_count": cols * rows,
        "target_h_ratio": median_or_default(h_ratios, 0.75),
        "target_w_ratio": median_or_default(w_ratios, 0.8),
        "baseline_ratio": median_or_default(bottom_ratios, 0.9),
        "samples": len(h_ratios),
    }


def flatten_layout_ids(layout_data: dict) -> list[int]:
    rows = layout_data.get("rows", [])
    flattened: list[int] = []
    for row in rows:
        for value in row:
            flattened.append(int(value))
    return flattened


def assign_frame_ids(ids: list[int], frame_count: int, fill_mode: str) -> list[int]:
    if not ids:
        raise ValueError("No ids available for frame assignment.")

    assigned: list[int] = []
    if fill_mode == "cycle":
        for i in range(frame_count):
            assigned.append(ids[i % len(ids)])
        return assigned

    last_id = ids[-1]
    for i in range(frame_count):
        assigned.append(ids[i] if i < len(ids) else last_id)
    return assigned


def split_vertical_strip(image: Image.Image, segments: int) -> list[Image.Image]:
    if segments <= 1:
        return [image.copy()]

    out: list[Image.Image] = []
    width, height = image.size
    for i in range(segments):
        y0 = round(i * height / segments)
        y1 = round((i + 1) * height / segments)
        y1 = max(y0 + 1, y1)
        out.append(image.crop((0, y0, width, y1)))
    return out


def clamp_u8(value: float) -> int:
    if value <= 0:
        return 0
    if value >= 255:
        return 255
    return int(round(value))


def defringe_white_matte(sprite: Image.Image) -> Image.Image:
    rgba = sprite.convert("RGBA")
    px = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = px[x, y]
            if a <= 0:
                px[x, y] = (0, 0, 0, 0)
                continue
            if a >= 254:
                continue

            alpha = a / 255.0
            # Assume light matte fringe and recover straight color from premixed edge.
            nr = clamp_u8((r - 255.0 * (1.0 - alpha)) / alpha)
            ng = clamp_u8((g - 255.0 * (1.0 - alpha)) / alpha)
            nb = clamp_u8((b - 255.0 * (1.0 - alpha)) / alpha)
            px[x, y] = (nr, ng, nb, a)
    return rgba


def resize_premultiplied(sprite: Image.Image, new_w: int, new_h: int) -> Image.Image:
    rgba = sprite.convert("RGBA")
    r, g, b, a = rgba.split()

    r_p = ImageChops.multiply(r, a).resize((new_w, new_h), Image.Resampling.LANCZOS)
    g_p = ImageChops.multiply(g, a).resize((new_w, new_h), Image.Resampling.LANCZOS)
    b_p = ImageChops.multiply(b, a).resize((new_w, new_h), Image.Resampling.LANCZOS)
    a_r = a.resize((new_w, new_h), Image.Resampling.LANCZOS)

    out = Image.merge("RGBA", (r_p, g_p, b_p, a_r))
    px = out.load()
    width, height = out.size
    for y in range(height):
        for x in range(width):
            pr, pg, pb, pa = px[x, y]
            if pa <= 0:
                px[x, y] = (0, 0, 0, 0)
                continue
            rr = clamp_u8(pr * 255.0 / pa)
            gg = clamp_u8(pg * 255.0 / pa)
            bb = clamp_u8(pb * 255.0 / pa)
            px[x, y] = (rr, gg, bb, pa)
    return out


def cleanup_alpha_noise(sprite: Image.Image, threshold: int = 6) -> Image.Image:
    rgba = sprite.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda v: 0 if v < threshold else v)
    rgba.putalpha(alpha)
    return rgba


def add_black_outline(
    sprite: Image.Image,
    size: int,
    alpha_value: int,
    solid_threshold: int,
) -> Image.Image:
    if size <= 0:
        return sprite

    rgba = sprite.convert("RGBA")
    body = rgba.getchannel("A").point(lambda v: 255 if v >= solid_threshold else 0)
    expanded = body
    for _ in range(size):
        expanded = expanded.filter(ImageFilter.MaxFilter(3))
    outline_mask = ImageChops.subtract(expanded, body)

    alpha_value = max(0, min(255, int(alpha_value)))
    if alpha_value < 255:
        outline_mask = outline_mask.point(lambda v: clamp_u8(v * alpha_value / 255.0))

    outline = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    outline.putalpha(outline_mask)
    return Image.alpha_composite(outline, rgba)


def blacken_light_outer_fringe(
    sprite: Image.Image,
    alpha_max: int,
    luma_min: int,
    chroma_max: int,
) -> Image.Image:
    rgba = sprite.convert("RGBA")
    width, height = rgba.size
    src = rgba.load()
    alpha = rgba.getchannel("A").load()

    out = rgba.copy()
    dst = out.load()

    alpha_max = max(1, min(255, int(alpha_max)))
    luma_min = max(0, min(255, int(luma_min)))
    chroma_max = max(0, min(255, int(chroma_max)))

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a <= 0 or a > alpha_max:
                continue

            spread = max(r, g, b) - min(r, g, b)
            if spread > chroma_max:
                continue
            luma = int(round(0.299 * r + 0.587 * g + 0.114 * b))
            if luma < luma_min:
                continue

            is_outer = False
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if nx == x and ny == y:
                        continue
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        is_outer = True
                        break
                    if alpha[nx, ny] == 0:
                        is_outer = True
                        break
                if is_outer:
                    break

            if is_outer:
                dst[x, y] = (0, 0, 0, a)

    return out


def force_black_edge_band(
    sprite: Image.Image,
    edge_width: int,
    alpha_floor: int,
) -> Image.Image:
    if edge_width <= 0:
        return sprite

    rgba = sprite.convert("RGBA")
    alpha = rgba.getchannel("A")
    # Treat any non-zero alpha as object mask so the true visual outer ring is covered.
    mask = alpha.point(lambda v: 255 if v > 0 else 0)
    inner = mask
    for _ in range(max(1, edge_width)):
        inner = inner.filter(ImageFilter.MinFilter(3))
    edge_band = ImageChops.subtract(mask, inner)

    out = rgba.copy()
    px = out.load()
    edge_px = edge_band.load()
    width, height = out.size
    alpha_floor = max(0, min(255, int(alpha_floor)))

    for y in range(height):
        for x in range(width):
            if edge_px[x, y] <= 0:
                continue
            r, g, b, a = px[x, y]
            if a <= 0:
                continue
            na = a if alpha_floor <= 0 else max(a, alpha_floor)
            px[x, y] = (0, 0, 0, na)

    return out


def compose_grid(
    objects_path: Path,
    layout_path: Path,
    crops_dir: Path,
    reference_path: Path,
    frame_w: int,
    frame_h: int,
    output_png: Path,
    output_webp: Path,
    report_path: Path,
    fill_mode: str,
    alpha_threshold: int,
    defringe_white: bool,
    outline_size: int,
    outline_alpha: int,
    outline_threshold: int,
    sharpen: bool,
    blacken_fringe: bool,
    fringe_alpha_max: int,
    fringe_luma_min: int,
    fringe_chroma_max: int,
    fringe_iterations: int,
    force_black_edge_width: int,
    force_black_edge_alpha_floor: int,
) -> None:
    objects_data = load_json(objects_path)
    layout_data = load_json(layout_path)

    analysis = analyze_reference_cells(
        reference_path=reference_path,
        frame_w=frame_w,
        frame_h=frame_h,
        alpha_threshold=alpha_threshold,
    )

    cols = int(analysis["cols"])
    rows = int(analysis["rows"])
    frame_count = int(analysis["frame_count"])
    canvas_w = cols * frame_w
    canvas_h = rows * frame_h

    object_map = {int(item["id"]): item for item in objects_data.get("objects", [])}
    source_ids = flatten_layout_ids(layout_data)

    valid_ids: list[int] = []
    missing_ids: list[int] = []
    for sprite_id in source_ids:
        item = object_map.get(int(sprite_id))
        if item is None:
            missing_ids.append(int(sprite_id))
            continue
        crop_path = crops_dir / item["file_name"]
        if not crop_path.exists():
            missing_ids.append(int(sprite_id))
            continue
        valid_ids.append(int(sprite_id))

    if not valid_ids:
        raise ValueError(f"No usable ids from layout: {layout_path}")

    # Special case for assets extracted as vertical strips:
    # when selected ids match grid columns and every crop is a tall column,
    # split each column into row-count slices so each grid cell gets one frame.
    strip_mode = False
    strip_columns: list[list[Image.Image]] = []
    if len(valid_ids) == cols:
        strip_mode = True
        for sprite_id in valid_ids:
            item = object_map[sprite_id]
            sprite_path = crops_dir / item["file_name"]
            with Image.open(sprite_path) as im:
                sprite = im.convert("RGBA")
            if sprite.height < frame_h * 2 or sprite.width > frame_w:
                strip_mode = False
                break
            strip_columns.append(split_vertical_strip(sprite, segments=rows))
        if not strip_mode:
            strip_columns = []

    assigned_ids = assign_frame_ids(valid_ids, frame_count=frame_count, fill_mode=fill_mode)

    target_h_ratio = float(analysis["target_h_ratio"])
    target_w_ratio = float(analysis["target_w_ratio"])
    baseline_ratio = float(analysis["baseline_ratio"])

    target_h = max(16, min(frame_h, round(frame_h * target_h_ratio)))
    max_w = max(16, min(frame_w, round(frame_w * min(0.98, max(0.5, target_w_ratio * 1.08)))))
    baseline_local = max(1, min(frame_h, round(frame_h * baseline_ratio)))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    placements: list[dict] = []

    for frame_index in range(frame_count):
        row = frame_index // cols
        col = frame_index % cols
        cell_x = col * frame_w
        cell_y = row * frame_h

        if strip_mode:
            sprite_id = valid_ids[col]
            sprite = strip_columns[col][row]
        else:
            sprite_id = assigned_ids[frame_index]
            item = object_map[sprite_id]
            sprite_path = crops_dir / item["file_name"]
            with Image.open(sprite_path) as im:
                sprite = im.convert("RGBA")

        if defringe_white:
            sprite = defringe_white_matte(sprite)
        sprite = cleanup_alpha_noise(sprite, threshold=6)

        scale_h = target_h / max(1, sprite.height)
        scale_w = max_w / max(1, sprite.width)
        scale = min(scale_h, scale_w)

        new_w = max(1, round(sprite.width * scale))
        new_h = max(1, round(sprite.height * scale))
        resized = resize_premultiplied(sprite, new_w, new_h)
        if sharpen:
            resized = resized.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=2))
        if outline_size > 0:
            resized = add_black_outline(
                resized,
                size=outline_size,
                alpha_value=outline_alpha,
                solid_threshold=outline_threshold,
            )
        if blacken_fringe:
            for _ in range(max(1, int(fringe_iterations))):
                resized = blacken_light_outer_fringe(
                    resized,
                    alpha_max=fringe_alpha_max,
                    luma_min=fringe_luma_min,
                    chroma_max=fringe_chroma_max,
                )
        if force_black_edge_width > 0:
            resized = force_black_edge_band(
                resized,
                edge_width=force_black_edge_width,
                alpha_floor=force_black_edge_alpha_floor,
            )

        x = cell_x + (frame_w - new_w) // 2
        y = cell_y + baseline_local - new_h
        if y < cell_y:
            y = cell_y
        if y + new_h > cell_y + frame_h:
            y = cell_y + frame_h - new_h

        canvas.alpha_composite(resized, (x, y))
        placements.append(
            {
                "frame_index": frame_index,
                "id": int(sprite_id),
                "row": row + 1,
                "column": col + 1,
                "source_mode": "strip-slice" if strip_mode else "single-frame",
                "x": x,
                "y": y,
                "width": new_w,
                "height": new_h,
            }
        )

    ensure_parent(output_png)
    canvas.save(output_png)
    ensure_parent(output_webp)
    canvas.save(output_webp, format="WEBP", lossless=True, quality=95, method=6)

    report = {
        "reference": str(reference_path),
        "frame": {"width": frame_w, "height": frame_h},
        "grid": {"cols": cols, "rows": rows, "count": frame_count},
        "analysis": {
            "samples": int(analysis["samples"]),
            "target_h_ratio": target_h_ratio,
            "target_w_ratio": target_w_ratio,
            "baseline_ratio": baseline_ratio,
            "resolved_target_h": target_h,
            "resolved_max_w": max_w,
            "resolved_baseline": baseline_local,
        },
        "postprocess": {
            "defringe_white": bool(defringe_white),
            "outline_size": int(outline_size),
            "outline_alpha": int(max(0, min(255, outline_alpha))),
            "outline_threshold": int(max(0, min(255, outline_threshold))),
            "sharpen": bool(sharpen),
            "blacken_fringe": bool(blacken_fringe),
            "fringe_alpha_max": int(max(0, min(255, fringe_alpha_max))),
            "fringe_luma_min": int(max(0, min(255, fringe_luma_min))),
            "fringe_chroma_max": int(max(0, min(255, fringe_chroma_max))),
            "fringe_iterations": int(max(1, fringe_iterations)),
            "force_black_edge_width": int(max(0, force_black_edge_width)),
            "force_black_edge_alpha_floor": int(max(0, min(255, force_black_edge_alpha_floor))),
        },
        "layout_ids": source_ids,
        "usable_ids": valid_ids,
        "missing_ids": missing_ids,
        "fill_mode": fill_mode,
        "strip_mode": strip_mode,
        "assigned_ids": assigned_ids,
        "placements": placements,
    }
    ensure_parent(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Composed {len(placements)} frames as strict grid {cols}x{rows}")
    print(f"- reference: {reference_path}")
    print(f"- frame size: {frame_w}x{frame_h}")
    print(f"- output png: {output_png}")
    print(f"- output webp: {output_webp}")
    print(f"- report: {report_path}")


def main() -> None:
    args = parse_args()
    job_dir = Path(args.job_dir)

    objects_path = Path(args.objects) if args.objects else job_dir / "extract" / "objects.json"
    layout_path = Path(args.layout) if args.layout else job_dir / "layout.json"
    crops_dir = Path(args.crops_dir) if args.crops_dir else job_dir / "extract" / "crops"

    reference_path = discover_reference_path(job_dir=job_dir, explicit=args.reference)
    if reference_path is None:
        raise FileNotFoundError(f"Reference image not found under: {job_dir}")

    output_png = Path(args.output) if args.output else job_dir / "output" / "final3.png"
    output_webp = Path(args.output_webp) if args.output_webp else job_dir / "output" / "final3.webp"
    report_path = Path(args.report) if args.report else job_dir / "output" / "composition3.json"

    compose_grid(
        objects_path=objects_path,
        layout_path=layout_path,
        crops_dir=crops_dir,
        reference_path=reference_path,
        frame_w=max(1, int(args.frame_width)),
        frame_h=max(1, int(args.frame_height)),
        output_png=output_png,
        output_webp=output_webp,
        report_path=report_path,
        fill_mode=args.fill_mode,
        alpha_threshold=max(0, min(255, int(args.alpha_threshold))),
        defringe_white=bool(args.defringe_white),
        outline_size=max(0, int(args.outline_size)),
        outline_alpha=max(0, min(255, int(args.outline_alpha))),
        outline_threshold=max(0, min(255, int(args.outline_threshold))),
        sharpen=bool(args.sharpen),
        blacken_fringe=bool(args.blacken_fringe),
        fringe_alpha_max=max(0, min(255, int(args.fringe_alpha_max))),
        fringe_luma_min=max(0, min(255, int(args.fringe_luma_min))),
        fringe_chroma_max=max(0, min(255, int(args.fringe_chroma_max))),
        fringe_iterations=max(1, int(args.fringe_iterations)),
        force_black_edge_width=max(0, int(args.force_black_edge_width)),
        force_black_edge_alpha_floor=max(0, min(255, int(args.force_black_edge_alpha_floor))),
    )


if __name__ == "__main__":
    main()
