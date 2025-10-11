#!/usr/bin/env python3
r"""
Pattern Creature Generator for SIFT/Hessian-Affine–friendly synthetic datasets
==============================================================================

Goal
----
Given an identity string (e.g., "zebra-001"), deterministically render a cute
"pattern creature" with dense, multi-scale, high-contrast features that are
stable under small affine/photometric changes. Distinctive, ID-specific glyphs
are placed at consistent anchor locations; non-distinctive micro-texture fills
provide additional keypoints. Variants of the same ID preserve spatial layout
(with jitter/affine noise) to test matching robustness.

Outputs
-------
- PNG images per ID and variant
- A JSON metadata file containing random seed, anchor locations, and transform
  parameters to aid inspection/debugging.
- Optional debug overlays with SIFT/DoG keypoints (requires OpenCV SIFT/DoG)

Dependencies
------------
- numpy
- pillow (PIL)
- opencv-python (cv2)  # optional but recommended for keypoint visualization

Usage
-----
python synthetic_creature.py \
    --outdir ./synthetic_creatures \
    --ids zebra-001 zebra-002 zebra-003 \
    --per-id 6 \
    --size 768 \
    --seed 0 \
    --show-kp  # optional, write *_kp.png with detected keypoints

Notes
-----
- Distinctive glyphs: ID-hash encoded 8x8 bit-matrices, ringed bullseyes,
  star-corner rosettes, and checker tiles with unique rotations.
- Non-distinctive textures: multiscale stippling, line hatching, and subtle
  Perlin-like value noise; all high-contrast to trigger DoG/Hessian responses.
- Variations: global similarity + mild affine, illumination (gamma/contrast),
  blur noise, additive Gaussian, small occluders.
- Spatial consistency: anchors are generated in normalized creature space and
  transformed by the same per-variant homography so the layout stays coherent.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Tuple, Dict, List

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops  # NOQA
from PIL import ImageEnhance  # NOQA
import kwarray
import kwimage

try:
    import cv2  # optional
except Exception:
    cv2 = None

# Import the new package
from ibeis.demo.pattern import (
    RenderParams,
    random_params,
    render_id_pattern_layer,
    seed_from_string,
)
from ibeis.demo.utils import id_to_color_pair, diagonal_gradient # NOQA


def draw_cartoon_animal(size: int):
    """
    Draw a simple cartoon quadruped with head, body, *thick rectangular* legs,
    eyes, and a *thick rectangular* tail.

    Returns:
        Dict with fields:
            image (RGBA): rendered creature
            mask_body (L): mask of the main body ellipse
            mask_full (L): mask covering body + tail + legs + head
            body_bbox (tuple[int, int, int, int])
            head_bbox (tuple[int, int, int, int])
            leg_boxes (List[tuple[int, int, int, int]])
            tail_poly (List[tuple[int, int]])

    CommandLine:
        xdoctest -m ibeis.demo.synthetic_creature draw_cartoon_animal --show

    Example:
        >>> import numpy as np
        >>> from ibeis.demo.synthetic_creature import draw_cartoon_animal
        >>> info = draw_cartoon_animal(256)
        >>> img, mask_body, mask_full = info['image'], info['mask_body'], info['mask_full']
        >>> assert img.mode == 'RGBA'
        >>> assert mask_body.mode == 'L' and mask_full.mode == 'L'
        >>> assert isinstance(info['body_bbox'], tuple) and len(info['body_bbox']) == 4
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(np.asarray(img), fnum=1, pnum=(1, 3, 1), doclf=True, title='cartoon (rgba)')
        >>> kwplot.imshow(np.asarray(mask_body), fnum=1, pnum=(1, 3, 2), title='mask: body')
        >>> kwplot.imshow(np.asarray(mask_full), fnum=1, pnum=(1, 3, 3), title='mask: full')
        >>> kwplot.show_if_requested()

    Example:
        >>> # Grid of different sizes (kwimage-style visual)
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.synthetic_creature import draw_cartoon_animal
        >>> sizes = [128, 192, 256, 384]
        >>> canvases = []
        >>> for s in sizes:
        ...     info = draw_cartoon_animal(s)
        ...     rgba = np.array(info['image'])[..., :3]
        ...     rgb = kwimage.ensure_float01(rgba)
        ...     rgb = kwimage.draw_header_text(rgb, f'size={s}')
        ...     canvases.append((rgb * 255).astype(np.uint8))
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=2, pad=8, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='cartoon grid'); kwplot.show_if_requested()
    """

    W = H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    outline = (10, 10, 10, 255)
    bodycolor = kwimage.Color.coerce('#A9957BFF').as255()

    # --- Body ellipse ---
    body_w = int(0.58 * W)
    body_h = int(0.38 * H)
    cx, cy = int(0.52 * W), int(0.58 * H)
    body_bbox = (cx - body_w // 2, cy - body_h // 2, cx + body_w // 2, cy + body_h // 2)

    # Masks
    mask_body = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask_body).ellipse(body_bbox, fill=255)

    mask_full = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask_full)
    md.ellipse(body_bbox, fill=255)

    # Paint body
    d.ellipse(body_bbox, outline=outline, fill=bodycolor, width=max(2, size // 256))

    # --- Legs as thick vertical rectangles ---
    leg_len = int(0.16 * H)
    leg_w = max(4, int(0.04 * body_w))  # thicker than before
    leg_xs = [
        int(cx - 0.22 * body_w),
        int(cx - 0.07 * body_w),
        int(cx + 0.07 * body_w),
        int(cx + 0.22 * body_w),
    ]
    y0 = body_bbox[3] - int(0.09 * body_h)
    leg_boxes = []
    for x in leg_xs:
        box = (x - leg_w // 2, y0, x + leg_w // 2, y0 + leg_len)
        # fill legs and outline
        d.rectangle(box, fill=bodycolor, outline=outline, width=max(2, size // 256))
        md.rectangle(box, fill=255)
        leg_boxes.append(box)

    # --- Head ellipse ---
    head_r = int(0.12 * W)
    hx, hy = int(0.26 * W), int(0.35 * H)
    head_bb = (hx - head_r, hy - head_r, hx + head_r, hy + head_r)
    d.ellipse(head_bb, outline=outline, width=max(2, size // 256), fill=bodycolor)
    md.ellipse(head_bb, fill=255)

    # Eyes
    er = max(2, size // 128) * 2
    d.ellipse((hx - head_r // 3 - er, hy - er, hx - head_r // 3 + er, hy + er), fill=outline)
    d.ellipse((hx + head_r // 3 - er, hy - er, hx + head_r // 3 + er, hy + er), fill=outline)
    er = max(2, size // 128) * 0.5
    pupil_color = (255, 255, 255, 255)
    d.ellipse((hx - head_r // 3 - er, hy - er, hx - head_r // 3 + er, hy + er), fill=pupil_color)
    d.ellipse((hx + head_r // 3 - er, hy - er, hx + head_r // 3 + er, hy + er), fill=pupil_color)

    # Smile
    sR = int(0.6 * head_r)
    d.arc((hx - sR // 2, hy - sR // 4, hx + sR // 2, hy + sR // 2),
          start=20, end=160, fill=outline, width=max(2, size // 256))

    # --- Tail as a thick rotated rectangle ---
    # previous tail points (tx0, ty0) to (tx1, ty1)
    tx0, ty0 = body_bbox[2] - int(0.05 * body_w), int(0.52 * H)
    tx1, ty1 = tx0 + int(0.10 * W), ty0 - int(0.08 * H)
    tail_w = max(6, int(0.07 * body_w))  # thicker tail
    # build rotated rectangle polygon around segment p0->p1
    vx, vy = (tx1 - tx0), (ty1 - ty0)
    L = math.hypot(vx, vy) or 1.0
    nx, ny = (-vy / L, vx / L)  # unit normal
    ox, oy = (nx * (tail_w / 2), ny * (tail_w / 2))
    p0 = (tx0 - ox, ty0 - oy)
    p1 = (tx0 + ox, ty0 + oy)
    p2 = (tx1 + ox, ty1 + oy)
    p3 = (tx1 - ox, ty1 - oy)
    tail_poly = [p0, p1, p2, p3]
    d.polygon(tail_poly, fill=bodycolor, outline=outline)
    md.polygon(tail_poly, fill=255)

    return {
        "image": img,
        "mask_body": mask_body,
        "mask_full": mask_full,
        "body_bbox": body_bbox,
        "head_bbox": head_bb,
        "leg_boxes": leg_boxes,
        "tail_poly": tail_poly,
        "size": size,
    }


# --------------- Warp helpers (remain here) ---------------
def _ellipse_map(u: float, v: float, bbox: Tuple[int, int, int, int]):
    x0, y0, x1, y1 = bbox
    a = (x1 - x0) * 0.5
    b = (y1 - y0) * 0.5
    cx = x0 + a
    cy = y0 + b
    X = (u - 0.5) * 2.0
    Y = (v - 0.5) * 2.0
    r2 = X * X + Y * Y
    bulge = 1.0 - 0.08 * r2
    return cx + a * X * bulge, cy + b * Y * bulge


def warp_pattern_into_ellipse(
    pattern_img: Image.Image,
    body_bbox: Tuple[int, int, int, int],
    canvas_size: Tuple[int, int],
):
    """
    Warp a rectangular pattern (L or RGB) into an elliptical body region
    using a vectorized inverse map (no mesh seams, higher detail).

    Notes:
        - Preserves the input mode (L/RGB).

    CommandLine:
        xdoctest -m ibeis.demo.synthetic_creature warp_pattern_into_ellipse --show

    Example:
        >>> # Grayscale case (kept for backward-compat with previous doctest)
        >>> import numpy as np
        >>> from PIL import Image
        >>> from ibeis.demo.synthetic_creature import warp_pattern_into_ellipse
        >>> pattern = Image.linear_gradient('L').resize((128, 128))
        >>> body_bbox = (64, 64, 192, 192)
        >>> warped = warp_pattern_into_ellipse(pattern, body_bbox, (256, 256))
        >>> assert warped.mode == 'L' and warped.size == (256, 256)
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl()
        >>> kwplot.imshow(np.asarray(pattern), fnum=1, doclf=True, title='input pattern (L)')
        >>> kwplot.imshow(np.asarray(warped), fnum=2, doclf=True, title='warped ellipse (L)')
        >>> kwplot.show_if_requested()

    Example:
        >>> # RGB case
        >>> import numpy as np
        >>> from PIL import Image, ImageOps
        >>> from ibeis.demo.synthetic_creature import warp_pattern_into_ellipse
        >>> # colorize a gray gradient to make a simple RGB texture
        >>> L = Image.linear_gradient('L').resize((128, 128))
        >>> RGB = ImageOps.colorize(L, black=(20, 60, 120), white=(220, 240, 255))
        >>> body_bbox = (64, 64, 192, 192)
        >>> warped_rgb = warp_pattern_into_ellipse(RGB, body_bbox, (256, 256))
        >>> assert warped_rgb.mode == 'RGB' and warped_rgb.size == (256, 256)
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl()
        >>> kwplot.imshow(np.asarray(RGB), fnum=1, doclf=True, title='input pattern (RGB)')
        >>> kwplot.imshow(np.asarray(warped_rgb), fnum=2, doclf=True, title='warped ellipse (RGB)')
        >>> kwplot.show_if_requested()

    Example:
        >>> # Grid: various ellipse aspect ratios (grayscale shown)
        >>> import numpy as np, kwimage
        >>> from PIL import Image
        >>> from ibeis.demo.synthetic_creature import warp_pattern_into_ellipse
        >>> pattern = Image.linear_gradient('L').resize((128, 128))
        >>> boxes = [(40, 80, 216, 176), (60, 60, 196, 196), (80, 40, 176, 216)]
        >>> canvases = []
        >>> for bbox in boxes:
        ...     im = warp_pattern_into_ellipse(pattern, bbox, (256, 256))
        ...     rgb = kwimage.ensure_float01(np.dstack([np.array(im)] * 3))
        ...     rgb = kwimage.draw_header_text(rgb, f'bbox={bbox}')
        ...     canvases.append((rgb * 255).astype(np.uint8))
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=3, pad=6, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='ellipse warp grid'); kwplot.show_if_requested()
    """
    import numpy as np

    # Normalize mode
    if pattern_img.mode == 'RGBA':
        pattern_img = pattern_img.convert('RGB')
    if pattern_img.mode not in {'L', 'RGB'}:
        pattern_img = pattern_img.convert('RGB')
    mode = pattern_img.mode
    is_rgb = (mode == 'RGB')

    W, H = canvas_size
    x0, y0, x1, y1 = body_bbox
    a = max(1.0, (x1 - x0) * 0.5)  # ellipse radii
    b = max(1.0, (y1 - y0) * 0.5)
    cx = x0 + a
    cy = y0 + b

    # Destination grid (only over bbox for speed)
    ww = int(x1 - x0)
    hh = int(y1 - y0)
    if ww <= 0 or hh <= 0:
        # degenerate bbox
        return Image.new(mode, (W, H), (255, 255, 255) if is_rgb else 255)

    yy, xx = np.mgrid[0:hh, 0:ww]
    Xd = (x0 + xx).astype(np.float32)
    Yd = (y0 + yy).astype(np.float32)

    # Compute normalized ellipse coords (initial guess)
    X = (Xd - cx) / a
    Y = (Yd - cy) / b

    # Inside-ellipse mask (final image will clip to this)
    inside = (X * X + Y * Y) <= 1.0

    # Invert your forward mapping:
    # forward: x = cx + a * X * bulge, y = cy + b * Y * bulge, bulge = (1 - 0.08*(X^2+Y^2))
    # Solve for X,Y given x,y via fixed-point iteration
    # Initialize with linear ellipse coords, then iterate 3–4 times.
    for _ in range(4):
        r2 = X * X + Y * Y
        bulge = (1.0 - 0.08 * r2).astype(np.float32)
        bulge = np.maximum(bulge, 1e-3)
        X = (Xd - cx) / (a * bulge)
        Y = (Yd - cy) / (b * bulge)

    # Convert to (u,v) in [0,1]x[0,1]
    u = (X + 1.0) * 0.5
    v = (Y + 1.0) * 0.5

    # Source sampling coordinates
    pw, ph = pattern_img.size
    # Clamp to valid range to avoid border artifacts
    u = np.clip(u, 0.0, 0.999999)
    v = np.clip(v, 0.0, 0.999999)
    sx = (u * pw).astype(np.float32)
    sy = (v * ph).astype(np.float32)

    # Vectorized bilinear sampling
    x0s = np.floor(sx).astype(np.int32)
    y0s = np.floor(sy).astype(np.int32)
    x1s = np.minimum(x0s + 1, pw - 1)
    y1s = np.minimum(y0s + 1, ph - 1)
    tx = sx - x0s
    ty = sy - y0s
    tx1 = 1.0 - tx
    ty1 = 1.0 - ty

    src = np.asarray(pattern_img)
    if not is_rgb:
        src = src[..., None]  # shape (ph, pw, 1) to reuse RGB code path

    # Gather 4 neighbors
    Ia = src[y0s, x0s]  # top-left
    Ib = src[y0s, x1s]  # top-right
    Ic = src[y1s, x0s]  # bottom-left
    Id = src[y1s, x1s]  # bottom-right

    # Blend
    top = Ia * (tx1[..., None]) + Ib * (tx[..., None])
    bot = Ic * (tx1[..., None]) + Id * (tx[..., None])
    sample = top * (ty1[..., None]) + bot * (ty[..., None])
    sample = sample.astype(np.uint8)

    # Put sampled bbox region into full canvas, clip with ellipse mask
    out = np.full((H, W, 3 if is_rgb else 1), 255, dtype=np.uint8)
    if is_rgb:
        out[y0:y1, x0:x1][inside] = sample[inside]
        out_img = Image.fromarray(out, mode='RGB')
    else:
        out[y0:y1, x0:x1][inside] = sample[inside]
        out_img = Image.fromarray(out[..., 0], mode='L')

    return out_img


def draw_forest_background(size: int, id_str: str, variant: int) -> Image.Image:
    """
    Draw a soft forest background with sky gradient, ground, and a random
    (but deterministic) placement of trees and bushes.
    The randomness is keyed on (id_str, variant) for reproducibility.

    CommandLine:
        xdoctest -m ibeis.demo.synthetic_creature draw_forest_background --show

    Example:
        >>> from ibeis.demo.synthetic_creature import draw_forest_background
        >>> img = draw_forest_background(256, 'forest-demo', 0)
        >>> assert img.mode == 'RGB' and img.size == (256, 256)
        >>> import numpy as np
        >>> arr = np.array(img)
        >>> assert (arr.mean() > 100) and (arr.std() > 10)
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(arr, fnum=1, doclf=True, title='draw_forest_background')
        >>> kwplot.show_if_requested()

    Example:
        >>> # Grid of ID/variant variations for visual regression
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.synthetic_creature import draw_forest_background
        >>> ids = ['forest-A', 'forest-B']
        >>> variants = [0, 1, 2]
        >>> canvases = []
        >>> for name in ids:
        ...     for v in variants:
        ...         im = draw_forest_background(192, name, v)
        ...         rgb = kwimage.ensure_float01(np.array(im))
        ...         rgb = kwimage.draw_header_text(rgb, f'{name} v{v}')
        ...         canvases.append((rgb * 255).astype(np.uint8))
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=len(variants), pad=8, bg_value='kitware_gray')
        >>> assert grid.ndim == 3
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(grid, fnum=1, doclf=True, title='forest background grid')
        >>> kwplot.show_if_requested()
    """
    from ibeis.demo.utils import diagonal_gradient, rng_from, value_noise  # NOQA
    W = H = size
    rng = rng_from(id_str, variant ^ 0xA11CE5)  # salt the variant for background

    # --- Sky gradient (top) and ground (bottom) ---
    # Sky: subtle blue gradient; Ground: green field with value-noise texture
    sky_top = (210, 230, 255)
    sky_bot = (150, 190, 245)
    sky = diagonal_gradient((W, H), sky_top, sky_bot, angle_deg=90.0)

    # Ground region
    ground_h = int(0.35 * H)
    ground_y0 = H - ground_h
    ground = Image.new("RGB", (W, ground_h), (70, 140, 70))
    # Texture the ground using value_noise for a natural look
    n = (value_noise(ground_h, W, rng, octaves=4) * 255).astype(np.uint8)
    tex = np.stack([n] * 3, axis=-1)
    g_arr = np.array(ground, dtype=np.int16)
    g_arr = np.clip(g_arr + (tex.astype(np.int16) - 128) // 5, 0, 255).astype(np.uint8)
    ground = Image.fromarray(g_arr, mode="RGB")

    bg = sky.copy()
    bg.paste(ground, (0, ground_y0))

    d = ImageDraw.Draw(bg)

    # --- Helpers to draw trees and bushes ---
    def draw_tree(x: int, base_y: int, scale: float):
        """Simple trunk + 2–3 foliage blobs with slight depth shading."""
        trunk_h = int(70 * scale)
        trunk_w = max(3, int(10 * scale))
        trunk_color = (90, 70, 50)
        d.rectangle([x - trunk_w // 2, base_y - trunk_h, x + trunk_w // 2, base_y], fill=trunk_color)
        # Foliage blobs (circles)
        fol_base = int(36 * scale)
        blobs = 2 + int(rng.integers(0, 2))
        for i in range(blobs):
            r = int(fol_base * (1.0 + 0.25 * rng.random()))
            cx = x + int(rng.uniform(-0.22, 0.22) * r * 2)
            cy = base_y - trunk_h - int(0.3 * r) - int(i * 0.25 * r)
            shade = int(28 * (0.5 - (cy / H)))
            green = np.clip(120 + shade + int(40 * rng.random()), 80, 170)
            col = (40 + shade, green, 40 + shade)
            bbox = [cx - r, cy - r, cx + r, cy + r]
            d.ellipse(bbox, fill=tuple(np.clip(col, 0, 255)))
        # simple shadow on ground
        sh_w = int(36 * scale)
        sh_y = base_y + 1
        d.ellipse([x - sh_w, sh_y - 5, x + sh_w, sh_y + 5], fill=(40, 80, 40))

    def draw_bush(x: int, base_y: int, scale: float):
        r = int(20 * scale)
        for k in range(2 + int(rng.integers(0, 2))):
            rr = int(r * (1.0 + 0.3 * rng.random()))
            cx = x + int(rng.uniform(-0.6, 0.6) * r)
            cy = base_y - int(rng.uniform(0.1, 0.4) * r)
            col = (60, 120 + int(40 * rng.random()), 60)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)

    # --- Layer distant, mid, and near vegetation for depth ---
    horizon_y = ground_y0
    bands = [
        # (count range, scale range, y jitter range)
        ((3, 6), (0.6, 0.9), (-0.05, 0.02)),   # far line of trees near horizon
        ((4, 8), (0.8, 1.2), (0.00, 0.08)),   # mid trees
        ((6, 12), (0.7, 1.1), (0.05, 0.15)),  # bushes in front
    ]
    # Trees
    n_far = rng.integers(*bands[0][0])
    for _ in range(int(n_far)):
        x = int(rng.uniform(0.05, 0.95) * W)
        y = horizon_y + int(rng.uniform(*bands[0][2]) * H)
        s = rng.uniform(*bands[0][1])
        draw_tree(x, y, s)
    n_mid = rng.integers(*bands[1][0])
    for _ in range(int(n_mid)):
        x = int(rng.uniform(0.03, 0.97) * W)
        y = horizon_y + int(rng.uniform(*bands[1][2]) * H)
        s = rng.uniform(*bands[1][1])
        draw_tree(x, y, s)
    # Bushes
    n_bush = rng.integers(*bands[2][0])
    for _ in range(int(n_bush)):
        x = int(rng.uniform(0.03, 0.97) * W)
        y = horizon_y + int(rng.uniform(*bands[2][2]) * H)
        s = rng.uniform(*bands[2][1])
        draw_bush(x, y, s)

    # slight blur to push the background back and reduce aliasing
    bg = bg.filter(ImageFilter.GaussianBlur(radius=max(0.6, size / 1024)))
    return bg


def compose_creature_body_pattern(params: RenderParams, debug: bool = False):
    """
    Compose a full synthetic creature with its patterned body, cartoon outline,
    gradient coloration, and optional blur/noise augmentations.

    This is the primary synthesis routine combining the cartoon base
    with the deterministic raster pattern built by `render_id_pattern_layer`.

    Returns:
        (creature RGB image, metadata dict)

    Compose a full synthetic creature by:
      1) building a standardized animal with body pattern applied,
      2) randomly affine-warping ONLY the animal (and its masks),
      3) pasting the warped animal onto an unwarped background (no blending),
      4) applying full-frame photometric tweaks.

    Returns:
        (final RGB image, metadata dict)

    CommandLine:
        xdoctest -m ibeis.demo.synthetic_creature compose_creature_body_pattern --show

    Example:
        >>> from ibeis.demo.synthetic_creature import *  # NOQA
        >>> from ibeis.demo.pattern import RenderParams
        >>> from ibeis.demo.synthetic_creature import compose_creature_body_pattern
        >>> #import kwarray
        >>> import random, string
        >>> label = random.choice(string.ascii_lowercase)
        >>> params = RenderParams(f'demo-animal-{label}', 0, canvas_size=756)
        >>> img, meta = compose_creature_body_pattern(params)
        >>> assert img.mode == 'RGB' and isinstance(meta, dict)
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(np.asarray(img), fnum=1, doclf=True, title=f"Creature {meta['id']}")
        >>> kwplot.show_if_requested()

    Example:
        >>> # Grid: visualize multiple IDs and variants
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.pattern import RenderParams
        >>> from ibeis.demo.synthetic_creature import compose_creature_body_pattern
        >>> ids = ['creature-A', 'creature-B', 'creature-C']
        >>> vars = [0, 1, 2, 4, 5]
        >>> canvases = []
        >>> for name in ids:
        ...     for v in vars:
        ...         #p = RenderParams(name, v, canvas_size=192)
        ...         p = RenderParams(name, variant=v, canvas_size=512)
        ...         im, meta = compose_creature_body_pattern(p)
        ...         rgb = kwimage.ensure_float01(np.array(im))
        ...         rgb = kwimage.draw_header_text(rgb, f"{name} v{v}")
        ...         canvases.append((rgb * 255).astype(np.uint8))
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=len(vars), pad=8, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='creature variants grid'); kwplot.show_if_requested()
    """
    size = params.canvas_size
    W = H = size

    # --- Unwarped background (kept untouched by the affine) ---
    background = draw_forest_background(size, params.id_str, params.variant)

    # --- Standardized animal + masks (body + full) ---
    animal_info = draw_cartoon_animal(size)
    cartoon_rgba  = animal_info['image']
    body_bbox     = animal_info['body_bbox']
    # mask_body_L   = animal_info['mask_body']      # body ellipse only (L)
    mask_full_L   = animal_info['mask_full']      # head+body+legs+tail (L)

    # --- Build body-space pattern and warp onto the body ellipse (full-canvas L) ---
    bw = body_bbox[2] - body_bbox[0]
    bh = body_bbox[3] - body_bbox[1]
    raw_pattern_rgb = render_id_pattern_layer(params, (bw, bh))

    c1, c2 = id_to_color_pair(params.id_str)
    grad = diagonal_gradient((bw, bh), c1, c2, angle_deg=45.0)
    ink_mask = ImageOps.invert(ImageOps.grayscale(raw_pattern_rgb))
    # 3) Paint gradient over dark parts of the pattern (outside body untouched)
    raw_pattern_rgb2 = raw_pattern_rgb.copy()
    raw_pattern_rgb2.paste(grad, mask=ink_mask)

    # pattern_L = ImageOps.grayscale(raw_pattern_rgb)
    warped_rgb = warp_pattern_into_ellipse(
        raw_pattern_rgb2, body_bbox, (W, H),
    )
    # warped_pattern_mask = ImageOps.invert(warped_pattern_L)
    # warped_rgb = pattern_L.convert('RGB')
    # warped_rgb.paste(grad, mask=warped_pattern_mask)

    # Start with a blank animal canvas, then paste the *exact* warped pattern into the body
    raw_body_rgb = Image.new("RGB", (W, H), (255, 255, 255))
    raw_body_rgb.paste(warped_rgb, mask=animal_info['mask_body'])  # exact body texture
    raw_body_rgb.paste(warped_rgb, mask=animal_info['mask_body'])  # exact body texture

    # Overlay the cartoon outlines to keep the drawing look
    animal_rgb = Image.new("RGB", (W, H), (255, 255, 255))

    # Paste the raw animal cartoon onto a white image
    animal_rgb.paste(cartoon_rgba, mask=mask_full_L)
    # animal_rgb.paste(raw_body_rgb, mask=mask_body_L)
    animal_rgb = ImageChops.darker(raw_body_rgb, animal_rgb)
    animal_rgb = ImageChops.multiply(raw_body_rgb, animal_rgb)

    # --- Build random affine that ONLY affects the animal (and corresponding masks) ---
    rng = kwarray.ensure_rng(params.id_str + str(params.variant))
    tf_center_to_origin = kwimage.Affine.coerce(offset=(-W // 2, -H // 2))
    tf_origin_to_center = kwimage.Affine.coerce(offset=(W // 2, H // 2))
    tf_rand = kwimage.Affine.random(rng=rng, scale=(0.95, 1.05), theta=(-0.1, 0.1), shear=None, translate=(0, 0))
    tf_animal = tf_origin_to_center @ tf_rand @ tf_center_to_origin

    # Warp the animal RGB (bilinear) and the masks (nearest) with identical transform
    animal_arr = np.asarray(animal_rgb)
    warped_animal_arr = kwimage.warp_image(animal_arr, transform=tf_animal, interpolation='linear')

    mask_full_arr = np.asarray(mask_full_L)
    warped_mask_full = kwimage.warp_image(mask_full_arr, transform=tf_animal, interpolation='nearest')
    warped_mask_full = np.clip(warped_mask_full, 0, 255).astype(np.uint8)

    # (Optional) also keep a warped body mask if needed downstream
    # mask_body_arr = np.asarray(mask_body_L)
    # warped_mask_body = kwimage.warp_image(mask_body_arr, transform=tf_animal, interpolation='nearest').astype(np.uint8)

    warped_animal_rgb = Image.fromarray(warped_animal_arr, mode='RGB')
    warped_mask_full_L = Image.fromarray(warped_mask_full, mode='L')

    # --- Paste the warped animal onto the original (unwarped) background with NO blending ---
    final_rgb = background.copy()
    final_rgb.paste(warped_animal_rgb, mask=warped_mask_full_L)

    # --- Global photometric tweaks on the full image (now includes background + animal) ---
    if params.blur_sigma > 0:
        final_rgb = final_rgb.filter(ImageFilter.GaussianBlur(radius=params.blur_sigma))
    if params.add_noise > 0:
        arr = np.array(final_rgb, dtype=np.float32)
        rng = np.random.default_rng(seed_from_string(params.id_str) ^ params.variant)
        arr += rng.normal(0, params.add_noise, arr.shape)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        final_rgb = Image.fromarray(arr, mode="RGB")

    meta = {
        "id": params.id_str,
        "variant": params.variant,
        "body_bbox": body_bbox,
        "contrast": params.contrast,
        "gamma": params.gamma,
        "blur_sigma": params.blur_sigma,
        "add_noise": params.add_noise,
        # Optionally expose the random affine params (matrix) for reproducibility
        "affine_matrix": tf_animal.matrix.tolist(),
    }

    if debug and cv2 is not None:
        overlay = np.array(final_rgb.convert("RGB"))
        gray = np.array(final_rgb.convert("L"))
        try:
            sift = cv2.SIFT_create()
            kps = sift.detect(gray, None)
        except Exception:
            Hc = cv2.cornerHarris(gray.astype(np.float32), 2, 3, 0.04)
            Hc = cv2.dilate(Hc, None)
            thresh = 0.01 * Hc.max()
            ys, xs = np.where(Hc > thresh)
            kps = [cv2.KeyPoint(float(x), float(y), 6) for x, y in zip(xs, ys)]
        overlay = cv2.drawKeypoints(
            overlay, kps, None, flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
        )
        return Image.fromarray(overlay), meta

    # final_rgb = raw_pattern_rgb
    # final_rgb = animal_rgb
    # final_rgb = grad

    return final_rgb, meta


# ---------------- Dataset utilities ----------------
def save_example(img: Image.Image, meta: Dict, outdir: Path, with_kp: bool):
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{meta['id']}__v{meta['variant']:02d}"
    img_path = outdir / f"{stem}.png"
    img.save(img_path)
    if with_kp and cv2 is not None:
        overlay, _ = compose_creature_body_pattern(
            RenderParams(
                meta["id"],
                meta["variant"],
                img.size[0],
                contrast=meta["contrast"],
                gamma=meta["gamma"],
                blur_sigma=meta["blur_sigma"],
                add_noise=meta["add_noise"],
            ),
            debug=True,
        )
        overlay.save(outdir / f"{stem}_kp.png")
    return img_path


def write_metadata(all_meta: List[Dict], outdir: Path):
    mpath = outdir / "metadata.json"
    with mpath.open("w") as f:
        json.dump(all_meta, f, indent=2)
    return mpath


# ---------------- CLI ----------------
def parse_args():
    ap = argparse.ArgumentParser(
        description="Generate SIFT-friendly pattern creatures for IBEIS testing"
    )
    ap.add_argument("--outdir", type=str, required=True)
    ap.add_argument(
        "--ids", nargs="*", type=str, default=["zebra-001", "zebra-002", "zebra-003"]
    )
    ap.add_argument("--per-id", type=int, default=5, help="number of variants per ID")
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="optional global seed to permute ID anchors",
    )
    ap.add_argument(
        "--show-kp",
        action="store_true",
        help="emit extra *_kp.png keypoint overlays (requires OpenCV)",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    if args.seed is not None:
        np.random.seed(args.seed)
    all_meta: List[Dict] = []
    for id_str in args.ids:
        for v in range(args.per_id):
            params = random_params(id_str, v, args.size)
            img, meta = compose_creature_body_pattern(params, debug=False)
            p = save_example(img, meta, outdir, with_kp=args.show_kp)
            all_meta.append({**meta, "path": str(p)})
    mpath = write_metadata(all_meta, outdir)
    print(f"Wrote {len(all_meta)} images to {outdir} and metadata to {mpath}")


if __name__ == "__main__":
    r"""
    python ~/code/ibeis/ibeis/demo/synthetic_creature.py \
      --outdir ./synthetic_creatures \
      --ids creature-001 creature-002 creature-003 creature-004  \
      --per-id 2 \
      --size 768
    """
    main()
