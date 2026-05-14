#!/usr/bin/env python3
"""
Generate landscape conference badges with QR for Bambu Studio + AMS.

Output policy:
- always writes in output/ by default
- one deterministic file per person: output/badge_<name>.3mf
"""

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
import zipfile

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from generate_3d_qr import OUTPUT_DIR, create_box_triangles, generate_qr_code, parse_size, qr_to_array

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

try:
    from svgpathtools import svg2paths

    SVGTOOLS_AVAILABLE = True
except ImportError:
    SVGTOOLS_AVAILABLE = False

try:
    from scipy import ndimage

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


DEFAULT_LOGO = "/Users/samthomson/Desktop/logo.svg"
DEFAULT_EVENT = "OSLO 2026"
DEFAULT_COMPANY_FONT = "Outfit"
DEFAULT_NAME_FONT = "Menlo"
BADGE_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "namebadges")


def cq_to_mesh(cq_obj):
    temp = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
    temp.close()
    try:
        cq.exporters.export(cq_obj, temp.name)
        return trimesh.load(temp.name)
    finally:
        if os.path.exists(temp.name):
            os.unlink(temp.name)


def concat_meshes(*meshes):
    valid = [m for m in meshes if m is not None]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]
    return trimesh.util.concatenate(valid)


def mesh_to_verts_tris_xml(mesh_obj, material_index):
    verts_xml = ""
    for v in mesh_obj.vertices:
        verts_xml += f'          <vertex x="{v[0]:.6f}" y="{v[1]:.6f}" z="{v[2]:.6f}" />\n'

    tris_xml = ""
    for f in mesh_obj.faces:
        tris_xml += f'          <triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}" pid="1" p1="{material_index}" />\n'
    return verts_xml, tris_xml


def safe_filename(text):
    base = (text or "badge").strip().lower()
    chars = []
    for ch in base:
        if ch.isalnum():
            chars.append(ch)
        elif ch in {" ", "-", "_"}:
            chars.append("_")
    out = "".join(chars).strip("_")
    return out or "badge"


def limit_text(text):
    if not text:
        return ""
    return " ".join(str(text).strip().split())


def ascii_text_or_none(text):
    text = limit_text(text)
    if not text:
        return None
    if all(ord(ch) < 128 for ch in text):
        return text
    return None


def estimate_mono_size_for_width(text, width_mm, default_size, min_size):
    text = limit_text(text)
    if not text:
        return min_size
    # Conservative character width to avoid overflow on long names.
    char_factor = 0.70
    est = width_mm / (len(text) * char_factor)
    return max(min_size, min(default_size, est))


def load_image_rgba(path):
    if not path or not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


def load_svg_mask(path, canvas_px=900, pad_px=50):
    """Rasterize simple SVG paths into a binary mask."""
    if not SVGTOOLS_AVAILABLE:
        print("  Warning: svgpathtools not available, cannot parse SVG logo.")
        return None
    try:
        paths, _ = svg2paths(path)
    except Exception as exc:
        print(f"  Warning: failed to parse SVG logo ({exc})")
        return None
    if not paths:
        return None

    xmins, xmaxs, ymins, ymaxs = [], [], [], []
    for p in paths:
        xmin, xmax, ymin, ymax = p.bbox()
        xmins.append(xmin)
        xmaxs.append(xmax)
        ymins.append(ymin)
        ymaxs.append(ymax)

    xmin, xmax = min(xmins), max(xmaxs)
    ymin, ymax = min(ymins), max(ymaxs)
    w = max(1e-6, xmax - xmin)
    h = max(1e-6, ymax - ymin)
    scale = min((canvas_px - 2 * pad_px) / w, (canvas_px - 2 * pad_px) / h)

    img = Image.new("L", (canvas_px, canvas_px), 0)
    draw = ImageDraw.Draw(img)
    for path_obj in paths:
        steps = max(240, int(path_obj.length(error=1e-3) * 2))
        points = []
        for i in range(steps + 1):
            t = i / steps
            pt = path_obj.point(t)
            x = (pt.real - xmin) * scale + pad_px
            y = (ymax - pt.imag) * scale + pad_px
            points.append((x, y))
        draw.polygon(points, fill=255)

    mask = np.array(img) > 127
    if not SCIPY_AVAILABLE:
        return mask

    # Smooth out tiny anti-aliased spikes from sampled SVG paths.
    structure = np.ones((2, 2), dtype=bool)
    mask = ndimage.binary_opening(mask, structure=structure)
    mask = ndimage.binary_closing(mask, structure=structure)

    labels, n = ndimage.label(mask)
    if n <= 1:
        return mask
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    largest = counts.argmax()
    keep = labels == largest
    return keep


def mask_to_mesh(
    mask,
    center_x,
    center_y,
    target_width_mm,
    base_z,
    height,
    max_width_px=480,
    min_pixel_mm=0.30,
):
    if mask is None or not np.any(mask):
        return None

    ys, xs = np.where(mask)
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    mask = mask[y0:y1, x0:x1]
    h_px, w_px = mask.shape

    if w_px > max_width_px:
        scale = max_width_px / w_px
        resized = Image.fromarray((mask * 255).astype(np.uint8)).resize(
            (max(1, int(w_px * scale)), max(1, int(h_px * scale))),
            Image.Resampling.NEAREST,
        )
        mask = np.array(resized) > 127
        h_px, w_px = mask.shape

    # Avoid microscopic voxelized boxes that explode triangle count.
    # We cap effective raster resolution by physical pixel size.
    pixel_mm = target_width_mm / max(1, w_px)
    if pixel_mm < min_pixel_mm:
        scale = pixel_mm / min_pixel_mm
        new_w = max(1, int(w_px * scale))
        new_h = max(1, int(h_px * scale))
        resized = Image.fromarray((mask * 255).astype(np.uint8)).resize(
            (new_w, new_h),
            Image.Resampling.NEAREST,
        )
        mask = np.array(resized) > 127
        h_px, w_px = mask.shape

    px = target_width_mm / w_px
    target_h_mm = h_px * px
    x0_mm = center_x - target_width_mm / 2 + px / 2
    y0_mm = center_y + target_h_mm / 2 - px / 2

    triangles = []
    for i in range(h_px):
        for j in range(w_px):
            if mask[i, j]:
                x = x0_mm + j * px
                y = y0_mm - i * px
                triangles.extend(create_box_triangles(x, y, base_z, px * 0.98, px * 0.98, height))

    if not triangles:
        return None
    tri = np.array(triangles)
    verts = tri.reshape(-1, 3)
    faces = np.arange(len(verts)).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces)
    mesh.merge_vertices()
    return mesh


def fit_width_to_box(mask, max_width_mm, max_height_mm):
    """Return a width that keeps the mask inside max width/height."""
    if mask is None or not np.any(mask):
        return max_width_mm

    ys, xs = np.where(mask)
    h_px = ys.max() - ys.min() + 1
    w_px = xs.max() - xs.min() + 1
    if w_px <= 0 or h_px <= 0:
        return max_width_mm

    width = max_width_mm
    height = width * (h_px / w_px)
    if height > max_height_mm:
        width = max_height_mm * (w_px / h_px)
    return max(1.0, width)


def emoji_to_codepoint_string(emoji):
    """Convert an emoji sequence to Twemoji codepoint naming format."""
    return "-".join(f"{ord(ch):x}" for ch in emoji)


def fetch_twemoji_mask(emoji):
    """Fetch a Twemoji PNG for the sequence and return alpha mask."""
    # Twemoji filenames often omit VS16 (FE0F). Try canonical variants.
    variants = []
    code = emoji_to_codepoint_string(emoji)
    variants.append(code)
    stripped = "".join(ch for ch in emoji if ord(ch) != 0xFE0F)
    if stripped and stripped != emoji:
        variants.append(emoji_to_codepoint_string(stripped))

    cache_dir = os.path.join(OUTPUT_DIR, ".emoji_cache")
    os.makedirs(cache_dir, exist_ok=True)

    for variant in variants:
        png_path = os.path.join(cache_dir, f"{variant}.png")
        if not os.path.exists(png_path):
            url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{variant}.png"
            try:
                with urllib.request.urlopen(url, timeout=8) as resp:
                    data = resp.read()
                with open(png_path, "wb") as fh:
                    fh.write(data)
            except urllib.error.URLError:
                continue
            except Exception:
                continue

        try:
            rgba = np.array(Image.open(png_path).convert("RGBA"))
            alpha = rgba[:, :, 3] > 10
            if np.any(alpha):
                return alpha
        except Exception:
            continue

    return None


def build_qr_mesh(url, qr_size_mm, center_x, center_y, base_z, qr_height=0.9):
    qr_img = generate_qr_code(url, size=220, border=1)
    qr_array = qr_to_array(qr_img)
    pixel_size = qr_size_mm / qr_array.shape[0]
    square_size = pixel_size * 0.95

    triangles = []
    for i in range(qr_array.shape[0]):
        for j in range(qr_array.shape[1]):
            if qr_array[i, j] == 1:
                x = center_x + (j - qr_array.shape[1] / 2) * pixel_size
                y = center_y + (qr_array.shape[0] / 2 - i) * pixel_size
                triangles.extend(create_box_triangles(x, y, base_z, square_size, square_size, qr_height))

    triangles = np.array(triangles)
    verts = triangles.reshape(-1, 3)
    faces = np.arange(len(verts)).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces)
    mesh.merge_vertices()
    return mesh


def build_qr_background_mesh(center_x, center_y, qr_size_mm, base_z, layer_height=0.6, pad=0.0):
    """Create a white underlay patch behind the QR area."""
    width = qr_size_mm + pad
    depth = qr_size_mm + pad
    triangles = np.array(create_box_triangles(center_x, center_y, base_z, width, depth, layer_height))
    verts = triangles.reshape(-1, 3)
    faces = np.arange(len(verts)).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces)
    mesh.merge_vertices()
    return mesh


def build_base_mesh(
    badge_width,
    badge_height,
    base_height,
    corner_radius=3.0,
    slot_length=11.0,
    slot_width=3.0,
    slot_top_margin=4.4,
    slot_side_margin=1.8,
):
    if not CADQUERY_AVAILABLE:
        triangles = np.array(create_box_triangles(0, 0, 0, badge_width, badge_height, base_height))
        verts = triangles.reshape(-1, 3)
        faces = np.arange(len(verts)).reshape(-1, 3)
        mesh = trimesh.Trimesh(vertices=verts, faces=faces)
        mesh.merge_vertices()
        print("  Warning: CadQuery unavailable; lanyard slots disabled.")
        return mesh

    base = (
        cq.Workplane("XY")
        .box(badge_width, badge_height, base_height)
        .edges("|Z")
        .fillet(corner_radius)
        .translate((0, 0, base_height / 2))
    )

    slot_y = badge_height / 2 - slot_top_margin
    slot_x = badge_width / 2 - slot_side_margin - slot_length / 2
    base = (
        base.faces(">Z")
        .workplane()
        .pushPoints([(-slot_x, slot_y), (slot_x, slot_y)])
        .slot2D(slot_length, slot_width, 0)
        .cutBlind(-(base_height + 1.0))
    )
    return cq_to_mesh(base)


def add_text_line(mesh, text, x, y, size, height, base_height, font_candidates, kind="bold"):
    if not CADQUERY_AVAILABLE or not text:
        return mesh

    last_err = None
    for font in font_candidates:
        try:
            text_obj = (
                cq.Workplane("XY")
                .workplane(offset=base_height)
                .center(x, y)
                .text(text, size, height, font=font, kind=kind)
            )
            return concat_meshes(mesh, cq_to_mesh(text_obj))
        except Exception as exc:
            last_err = exc
            continue
    print(f"  Warning: could not add text '{text}' ({last_err})")
    return mesh


def add_text_with_outline(
    fill_mesh,
    outline_mesh,
    text,
    x,
    y,
    size,
    height,
    base_height,
    font_candidates,
    kind="regular",
    outline_delta=0.6,
    top_lift=0.18,
    outline_height=None,
    fill_height=None,
):
    """Render text twice: larger underlay + normal foreground."""
    oh = height if outline_height is None else outline_height
    fh = height if fill_height is None else fill_height
    outline_mesh = add_text_line(
        outline_mesh,
        text,
        x,
        y,
        size + outline_delta,
        oh,
        base_height,
        font_candidates=font_candidates,
        kind=kind,
    )
    fill_mesh = add_text_line(
        fill_mesh,
        text,
        x,
        y,
        size,
        fh,
        base_height,
        font_candidates=font_candidates,
        kind=kind,
    )
    if fill_mesh is not None:
        fill_mesh.vertices[:, 2] += top_lift
    return fill_mesh, outline_mesh


def add_monospace_text_with_outline(
    fill_mesh,
    outline_mesh,
    text,
    center_x,
    y,
    size,
    height,
    base_height,
    font_candidates,
    kind="regular",
    outline_offset=0.22,
    top_lift=0.06,
    outline_height=None,
    fill_height=None,
    pitch_factor=0.62,
):
    """Draw outlined text one glyph at a time to keep alignment tight."""
    text = text or ""
    if not text:
        return fill_mesh, outline_mesh

    pitch = size * pitch_factor
    start_x = center_x - ((len(text) - 1) * pitch) / 2
    outline_offsets = [
        (-outline_offset, 0.0),
        (outline_offset, 0.0),
        (0.0, -outline_offset),
        (0.0, outline_offset),
        (-outline_offset * 0.75, -outline_offset * 0.75),
        (outline_offset * 0.75, -outline_offset * 0.75),
        (-outline_offset * 0.75, outline_offset * 0.75),
        (outline_offset * 0.75, outline_offset * 0.75),
    ]
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        x = start_x + i * pitch
        for dx, dy in outline_offsets:
            outline_mesh = add_text_line(
                outline_mesh,
                ch,
                x + dx,
                y + dy,
                size,
                height if outline_height is None else outline_height,
                base_height,
                font_candidates=font_candidates,
                kind=kind,
            )
        char_fill_mesh = add_text_line(
            None,
            ch,
            x,
            y,
            size,
            height if fill_height is None else fill_height,
            base_height,
            font_candidates=font_candidates,
            kind=kind,
        )
        char_fill_mesh = lift_mesh(char_fill_mesh, top_lift)
        fill_mesh = concat_meshes(fill_mesh, char_fill_mesh)
    return fill_mesh, outline_mesh


def build_pixel_marker_mesh(kind, center_x, center_y, target_width_mm, base_z, height):
    if kind == ">":
        mask = np.array(
            [
                [0, 0, 1, 0, 0],
                [0, 1, 1, 0, 0],
                [1, 1, 0, 1, 0],
                [1, 1, 0, 1, 0],
                [0, 1, 1, 0, 0],
                [0, 0, 1, 0, 0],
            ],
            dtype=bool,
        )
    else:
        mask = np.array(
            [
                [1, 1],
                [1, 1],
                [1, 1],
                [1, 1],
                [1, 1],
                [1, 1],
            ],
            dtype=bool,
        )
    return mask_to_mesh(mask, center_x, center_y, target_width_mm, base_z, height, max_width_px=24)


def build_logo_icon_mesh(logo_path, center_x, center_y, target_width_mm, base_z, height):
    if logo_path and logo_path.lower().endswith(".svg"):
        mask = load_svg_mask(logo_path)
    else:
        img = load_image_rgba(logo_path)
        if img is None:
            return None
        rgba = np.array(img)
        alpha = rgba[:, :, 3] > 20
        gray = np.dot(rgba[:, :, :3], np.array([0.299, 0.587, 0.114]))
        mask = alpha & (gray < 245)
    return mask_to_mesh(mask, center_x, center_y, target_width_mm, base_z, height, max_width_px=700)


def build_shape_mesh(
    shape,
    center_x,
    center_y,
    base_z,
    height,
    max_width_mm=27.0,
    max_height_mm=16.0,
    outline_iterations=0,
):
    shape = (shape or "").strip()
    if not shape:
        return None

    def native_mask():
        try:
            font = None
            for size in (160, 96, 64, 48, 40, 32):
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", size)
                    break
                except Exception:
                    continue
            if font is None:
                return None

            canvas = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), shape, font=font, embedded_color=True)
            if not bbox:
                return None
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w <= 0 or h <= 0:
                return None
            x = (400 - w) / 2 - bbox[0]
            y = (400 - h) / 2 - bbox[1]
            draw.text((x, y), shape, font=font, embedded_color=True)
            alpha = np.array(canvas)[:, :, 3] > 10
            if not np.any(alpha):
                return None
            return alpha
        except Exception:
            return None

    # Use native emoji style by default (matches system/ditto look).
    # Only force Twemoji first for ZWJ sequences that native stack may split.
    candidate_masks = []
    if "\u200d" in shape:
        twemoji = fetch_twemoji_mask(shape)
        if twemoji is not None:
            candidate_masks.append(twemoji)
        native = native_mask()
        if native is not None:
            if SCIPY_AVAILABLE:
                native = ndimage.binary_dilation(native, iterations=2)
                native = ndimage.binary_erosion(native, iterations=1)
            candidate_masks.append(native)
    else:
        native = native_mask()
        if native is not None:
            candidate_masks.append(native)
        twemoji = fetch_twemoji_mask(shape)
        if twemoji is not None:
            candidate_masks.append(twemoji)

    for mask in candidate_masks:
        target_w_mm = fit_width_to_box(mask, max_width_mm=max_width_mm, max_height_mm=max_height_mm)
        render_mask = mask
        if outline_iterations > 0 and SCIPY_AVAILABLE:
            render_mask = ndimage.binary_dilation(mask, iterations=outline_iterations)
        mesh = mask_to_mesh(render_mask, center_x, center_y, target_w_mm, base_z, height, max_width_px=260)
        if mesh is not None:
            return mesh

    return None


def lift_mesh(mesh, dz):
    """Return mesh with all vertices shifted up by dz."""
    if mesh is None or dz == 0:
        return mesh
    mesh.vertices[:, 2] += dz
    return mesh


def create_badge(
    url,
    output_file,
    name="Sam",
    shape="",
    company="Soapbox",
    company_font=DEFAULT_COMPANY_FONT,
    name_font=DEFAULT_NAME_FONT,
    event_line=DEFAULT_EVENT,
    logo_path=DEFAULT_LOGO,
    qr_size_mm=50,
    badge_width=112,
    badge_height=66,
    base_height=1.8,
    qr_height=0.6,
    qr_background_height=0.6,
    text_height=1.0,
):
    if badge_height < qr_size_mm + 2.5:
        raise ValueError("Badge height must be at least QR size + 2.5mm.")

    left_margin = 1.8
    hole_qr_inset = left_margin + 1.2
    qr_gap = 2.2
    qr_center_x = -badge_width / 2 + hole_qr_inset + qr_size_mm / 2
    slot_top_margin = 5.2
    slot_width = 3.0
    # Keep equal visual spacing: hole-to-QR top == QR bottom-to-badge edge.
    qr_top_gap = (badge_height - slot_top_margin - slot_width / 2 - qr_size_mm) / 2
    qr_top_gap = max(2.8, qr_top_gap)
    slot_bottom_y = badge_height / 2 - slot_top_margin - slot_width / 2
    qr_top = slot_bottom_y - qr_top_gap
    qr_center_y = qr_top - qr_size_mm / 2
    qr_right = qr_center_x + qr_size_mm / 2
    qr_bottom = qr_center_y - qr_size_mm / 2
    detail_base_z = base_height - 0.03

    panel_left = qr_right + qr_gap
    panel_right = badge_width / 2 - 2.2
    panel_width = panel_right - panel_left
    if panel_width < 23:
        raise ValueError("Right panel too narrow; increase badge width or reduce QR size.")

    base_mesh = build_base_mesh(
        badge_width=badge_width,
        badge_height=badge_height,
        base_height=base_height,
        slot_top_margin=slot_top_margin,
        slot_width=slot_width,
        slot_side_margin=hole_qr_inset,
    )
    # Sink a tiny amount into the white underlay to avoid visual hover gaps.
    qr_mesh = build_qr_mesh(
        url=url,
        qr_size_mm=qr_size_mm,
        center_x=qr_center_x,
        center_y=qr_center_y,
        base_z=detail_base_z + qr_background_height - 0.03,
        qr_height=qr_height,
    )
    qr_bg_mesh = build_qr_background_mesh(
        center_x=qr_center_x,
        center_y=qr_center_y,
        qr_size_mm=qr_size_mm,
        base_z=detail_base_z,
        layer_height=qr_background_height,
    )

    black_mesh = qr_mesh
    orange_mesh = None

    line_x = panel_left + 2.0
    top_line_y = qr_top - 5.3
    name_y = qr_top - 17.0
    shape_y = qr_top - 33.0
    event_y = max(qr_bottom + 3.8, -badge_height / 2 + 3.2)

    # Logo icon + company text (inline).
    icon_w = min(9.8, panel_width * 0.34)
    icon_cx = line_x + icon_w / 2
    logo_mesh = build_logo_icon_mesh(
        logo_path=logo_path,
        center_x=icon_cx,
        center_y=top_line_y,
        target_width_mm=icon_w,
        base_z=detail_base_z,
        height=text_height,
    )
    if logo_mesh is not None:
        orange_mesh = concat_meshes(orange_mesh, logo_mesh)

    company_text = ascii_text_or_none(company) or "SOAPBOX"
    company_left = line_x + icon_w + 0.25
    company_center = (company_left + panel_right) / 2
    company_size = estimate_mono_size_for_width(company_text, panel_right - company_left, 8.2, 3.8)
    orange_mesh = add_text_line(
        orange_mesh,
        company_text,
        company_center,
        top_line_y,
        company_size,
        text_height,
        detail_base_z,
        font_candidates=[company_font, "Outfit", "Arial"],
    )

    # Name line: centered block, aligned with shape/event center.
    mono_fonts = [name_font, "Menlo", "Menlo-Regular", "SFMono-Regular", "Courier New", "Monaco"]
    name_text = (ascii_text_or_none(name) or "unknown").lower()
    marker_w = 3.0
    gap = 0.8
    avail_for_name = panel_width - marker_w - gap - marker_w - 2.0
    # Keep glyphs printable for long names; tighten tracking before shrinking too far.
    name_size = estimate_mono_size_for_width(name_text, avail_for_name, 6.1, 3.6)
    pitch_factor = 0.62
    if name_text:
        needed = len(name_text) * (name_size * pitch_factor)
        if needed > avail_for_name:
            pitch_factor = max(0.48, avail_for_name / (len(name_text) * name_size))
    name_w = len(name_text) * name_size * pitch_factor
    text_center = (line_x + panel_right) / 2
    name_center = text_center
    name_left = name_center - name_w / 2
    bar_left = name_center + name_w / 2 + gap

    name_outline_h = max(0.5, text_height * 0.55)
    name_fill_h = max(0.5, text_height * 0.55)
    orange_mesh, black_mesh = add_monospace_text_with_outline(
        orange_mesh,
        black_mesh,
        name_text,
        name_center,
        name_y,
        name_size,
        text_height,
        detail_base_z,
        font_candidates=mono_fonts,
        kind="regular",
        outline_offset=0.20,
        top_lift=max(0.0, name_outline_h - 0.02),
        outline_height=name_outline_h,
        fill_height=name_fill_h,
        pitch_factor=pitch_factor,
    )

    # Render prompt/cursor as black-only accent.
    marker_size = max(3.8, name_size)
    marker_fill_h = max(0.5, text_height * 0.55)
    black_mesh = add_text_line(
        black_mesh,
        ">",
        name_left - gap - marker_w / 2,
        name_y,
        marker_size,
        marker_fill_h,
        detail_base_z,
        font_candidates=mono_fonts,
        kind="regular",
    )
    black_mesh = add_text_line(
        black_mesh,
        "|",
        bar_left + marker_w / 2,
        name_y,
        marker_size * 1.02,
        marker_fill_h,
        detail_base_z,
        font_candidates=mono_fonts,
        kind="regular",
    )

    # Shape line: normalize every emoji into the same large bbox.
    shape_box_width = 27.0
    shape_box_height = 16.0
    shape_outline_h = max(0.55, text_height * 0.60)
    shape_fill_h = max(0.55, text_height * 0.60)
    shape_mesh = build_shape_mesh(
        shape,
        (line_x + panel_right) / 2,
        shape_y + 1.0,
        detail_base_z + max(0.0, shape_outline_h - 0.02),
        shape_fill_h,
        max_width_mm=shape_box_width,
        max_height_mm=shape_box_height,
    )
    shape_outline_mesh = build_shape_mesh(
        shape,
        (line_x + panel_right) / 2,
        shape_y + 1.0,
        detail_base_z,
        shape_outline_h,
        max_width_mm=shape_box_width * 1.08,
        max_height_mm=shape_box_height * 1.08,
        outline_iterations=2,
    )
    if shape_outline_mesh is not None:
        black_mesh = concat_meshes(black_mesh, shape_outline_mesh)
    if shape_mesh is not None:
        orange_mesh = concat_meshes(orange_mesh, shape_mesh)
    else:
        orange_mesh = add_text_line(
            orange_mesh,
            "shape unavailable",
            (line_x + panel_right) / 2,
            shape_y,
            2.7,
            text_height * 0.9,
            detail_base_z,
            font_candidates=mono_fonts,
            kind="regular",
        )

    # Event line.
    event = ascii_text_or_none(event_line) or "OSLO 2026"
    event_size = estimate_mono_size_for_width(event, panel_width - 0.5, 4.4, 3.2)
    event_outline_h = max(0.5, text_height * 0.60)
    event_fill_h = max(0.5, text_height * 0.60)
    orange_mesh, black_mesh = add_monospace_text_with_outline(
        orange_mesh,
        black_mesh,
        event,
        (line_x + panel_right) / 2,
        event_y,
        event_size,
        max(1.1, text_height * 1.2),
        detail_base_z,
        font_candidates=mono_fonts,
        kind="bold",
        outline_offset=0.18,
        top_lift=max(0.0, event_outline_h - 0.02),
        outline_height=event_outline_h,
        fill_height=event_fill_h,
    )

    if orange_mesh is None:
        # Safety fallback so object id remains valid even if text/logo fail.
        orange_mesh = build_qr_background_mesh(
            center_x=panel_right - 0.8,
            center_y=-badge_height / 2 + 0.8,
            qr_size_mm=1.0,
            base_z=detail_base_z,
            layer_height=0.3,
            pad=0,
        )

    base_verts, base_tris = mesh_to_verts_tris_xml(base_mesh, 0)
    qr_bg_verts, qr_bg_tris = mesh_to_verts_tris_xml(qr_bg_mesh, 1)
    black_verts, black_tris = mesh_to_verts_tris_xml(black_mesh, 2)
    orange_verts, orange_tris = mesh_to_verts_tris_xml(orange_mesh, 3)

    model_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">
  <metadata name="Application">TreasureQR Badge Generator</metadata>
  <resources>
    <m:basematerials id="1">
      <m:base name="BaseTranslucentPurple" displaycolor="#7A3DB8" />
      <m:base name="QRWhiteUnderlay" displaycolor="#FFFFFF" />
      <m:base name="DetailBlack" displaycolor="#111111" />
      <m:base name="AccentOrange" displaycolor="#FF5A2A" />
    </m:basematerials>
    <object id="1" name="badge_base" type="model">
      <mesh>
        <vertices>
{base_verts}        </vertices>
        <triangles>
{base_tris}        </triangles>
      </mesh>
    </object>
    <object id="2" name="qr_underlay" type="model">
      <mesh>
        <vertices>
{qr_bg_verts}        </vertices>
        <triangles>
{qr_bg_tris}        </triangles>
      </mesh>
    </object>
    <object id="3" name="badge_details_black" type="model">
      <mesh>
        <vertices>
{black_verts}        </vertices>
        <triangles>
{black_tris}        </triangles>
      </mesh>
    </object>
    <object id="4" name="badge_details_orange" type="model">
      <mesh>
        <vertices>
{orange_verts}        </vertices>
        <triangles>
{orange_tris}        </triangles>
      </mesh>
    </object>
    <object id="5" name="badge" type="model">
      <components>
        <component objectid="1" />
        <component objectid="2" />
        <component objectid="3" />
        <component objectid="4" />
      </components>
    </object>
  </resources>
  <build>
    <item objectid="5" />
  </build>
</model>'''

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />
  <Default Extension="config" ContentType="text/xml" />
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>'''

    model_settings_config = '''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="1">
    <metadata key="extruder" value="1"/>
    <metadata key="name" value="badge_base"/>
  </object>
  <object id="2">
    <metadata key="extruder" value="2"/>
    <metadata key="name" value="qr_underlay"/>
  </object>
  <object id="3">
    <metadata key="extruder" value="3"/>
    <metadata key="name" value="badge_details_black"/>
  </object>
  <object id="4">
    <metadata key="extruder" value="4"/>
    <metadata key="name" value="badge_details_orange"/>
  </object>
  <object id="5">
    <metadata key="name" value="badge"/>
    <part id="1">
      <metadata key="extruder" value="1"/>
    </part>
    <part id="2">
      <metadata key="extruder" value="2"/>
    </part>
    <part id="3">
      <metadata key="extruder" value="3"/>
    </part>
    <part id="4">
      <metadata key="extruder" value="4"/>
    </part>
  </object>
</config>'''

    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", model_settings_config)

    print(f"✓ Created badge 3MF: {output_file}")
    print(f"  Badge size: {badge_width}mm x {badge_height}mm, QR: {qr_size_mm}mm")
    print(f"  QR margins top/bottom: {qr_top_gap:.1f}mm / {(qr_bottom + badge_height / 2):.1f}mm")
    print(f"  QR underlay/module heights: {qr_background_height:.2f}mm / {qr_height:.2f}mm")


def pick_member(members, member_query):
    q = member_query.strip().lower()
    for member in members:
        name = (member.get("name") or "").strip()
        if q == name.lower():
            return member
    raise ValueError(f"No member matched '{member_query}'.")


def member_label(member):
    return (member.get("name") or "Unknown").strip()


def create_badges_from_members(
    members_file,
    only_oslo,
    member_query,
    company,
    company_font,
    name_font,
    event_line,
    logo_path,
    qr_size_mm,
    badge_width,
    badge_height,
    base_height,
    qr_height,
    qr_background_height,
    text_height,
):
    with open(members_file, "r", encoding="utf-8") as fh:
        members = json.load(fh)

    if member_query:
        selected = [pick_member(members, member_query)]
    else:
        selected = [m for m in members if m.get("goingToOslo")]

    if not selected:
        raise ValueError("No members selected from the JSON file.")

    os.makedirs(BADGE_OUTPUT_DIR, exist_ok=True)
    for member in selected:
        url = member.get("followLink")
        if not url:
            print(f"  Skipping {member_label(member)} (missing followLink)")
            continue

        name = member_label(member)
        shape = member.get("shape") or ""
        output_file = os.path.join(BADGE_OUTPUT_DIR, f"badge_{safe_filename(name)}.3mf")
        print(f"  Generating badge for {name}...")
        create_badge(
            url=url,
            output_file=output_file,
            name=name,
            shape=shape,
            company=company,
            company_font=company_font,
            name_font=name_font,
            event_line=event_line,
            logo_path=logo_path,
            qr_size_mm=qr_size_mm,
            badge_width=badge_width,
            badge_height=badge_height,
            base_height=base_height,
            qr_height=qr_height,
            qr_background_height=qr_background_height,
            text_height=text_height,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate conference badges with QR + branding (Bambu AMS).")
    parser.add_argument("url", nargs="?", help="URL encoded into QR")
    parser.add_argument("--name", default="Sam", help="Display name")
    parser.add_argument("--shape", default="", help="Shape/emoji label")
    parser.add_argument("--company", default="Soapbox", help="Company name")
    parser.add_argument("--company-font", default=DEFAULT_COMPANY_FONT, help="Installed font name for company text")
    parser.add_argument("--name-font", default=DEFAULT_NAME_FONT, help="Installed monospace font name")
    parser.add_argument("--event-line", default=DEFAULT_EVENT, help="Bottom event line text")
    parser.add_argument("--logo", default=DEFAULT_LOGO, help="Logo path (SVG or PNG)")
    parser.add_argument("-s", "--size", default="medium", help="QR size preset or mm value")
    parser.add_argument("--badge-width", type=float, default=112, help="Badge width in mm")
    parser.add_argument("--badge-height", type=float, default=66, help="Badge height in mm")
    parser.add_argument("--base-height", type=float, default=1.8, help="Base thickness in mm")
    parser.add_argument("--qr-height", type=float, default=0.6, help="QR module raise height in mm")
    parser.add_argument("--qr-background-height", type=float, default=0.6, help="White QR underlay thickness in mm")
    parser.add_argument("--text-height", type=float, default=1.0, help="Raised text height in mm")
    parser.add_argument("--members-file", default=None, help="Generate from team members JSON")
    parser.add_argument("--member", default=None, help="Single member name from members file")
    parser.add_argument("--only-oslo", action="store_true", help="Only members with goingToOslo=true")
    parser.add_argument("-o", "--output", default=None, help="Output 3MF path (single badge mode)")
    args = parser.parse_args()

    qr_size_mm = parse_size(str(args.size))
    if args.members_file:
        create_badges_from_members(
            members_file=args.members_file,
            only_oslo=args.only_oslo,
            member_query=args.member,
            company=args.company,
            company_font=args.company_font,
            name_font=args.name_font,
            event_line=args.event_line,
            logo_path=args.logo,
            qr_size_mm=qr_size_mm,
            badge_width=args.badge_width,
            badge_height=args.badge_height,
            base_height=args.base_height,
            qr_height=args.qr_height,
            qr_background_height=args.qr_background_height,
            text_height=args.text_height,
        )
    else:
        if not args.url:
            parser.error("url is required unless --members-file is used")
        os.makedirs(BADGE_OUTPUT_DIR, exist_ok=True)
        output_file = args.output or os.path.join(BADGE_OUTPUT_DIR, f"badge_{safe_filename(args.name)}.3mf")
        create_badge(
            url=args.url,
            output_file=output_file,
            name=args.name,
            shape=args.shape,
            company=args.company,
            company_font=args.company_font,
            name_font=args.name_font,
            event_line=args.event_line,
            logo_path=args.logo,
            qr_size_mm=qr_size_mm,
            badge_width=args.badge_width,
            badge_height=args.badge_height,
            base_height=args.base_height,
            qr_height=args.qr_height,
            qr_background_height=args.qr_background_height,
            text_height=args.text_height,
        )
