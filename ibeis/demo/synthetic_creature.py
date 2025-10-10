#!/usr/bin/env python3
"""
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
python synth_creatures.py \
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
import dataclasses as dc
import hashlib
import json
import math
from pathlib import Path
from typing import Tuple, List, Dict

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops, ImageEnhance

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

# ------------------------------- utilities ---------------------------------


def seed_from_string(s: str) -> int:
    h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big", signed=False)


def rng_from(s: str, extra: int = 0) -> np.random.Generator:
    seed = seed_from_string(s) ^ (extra * 0x9E3779B185EBCA87)
    return np.random.default_rng(seed & ((1 << 63) - 1))


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


# ---------------------------- texture primitives ----------------------------


def draw_checker(draw: ImageDraw.ImageDraw, cx, cy, size, tiles, rot, fg, bg):
    """High-contrast checker rotated by rot degrees."""
    s = size
    img = Image.new("L", (s, s), color=bg)
    d = ImageDraw.Draw(img)
    step = s / tiles
    for i in range(tiles):
        for j in range(tiles):
            if (i + j) % 2 == 0:
                x0, y0 = i * step, j * step
                d.rectangle([x0, y0, x0 + step, y0 + step], fill=fg)
    img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    return img, (int(cx - img.width // 2), int(cy - img.height // 2))


def draw_bullseye(size: int, rings: int, fg: int, bg: int) -> Image.Image:
    """Concentric rings (DoG-friendly)."""
    img = Image.new("L", (size, size), color=bg)
    d = ImageDraw.Draw(img)
    for k in range(rings):
        r = size * (0.5 - 0.45 * (k / rings))
        bbox = [size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r]
        col = fg if k % 2 == 0 else bg
        d.ellipse(bbox, outline=col, width=max(1, size // 64))
    # center dot
    d.ellipse(
        [
            size / 2 - size * 0.02,
            size / 2 - size * 0.02,
            size / 2 + size * 0.02,
            size / 2 + size * 0.02,
        ],
        fill=fg,
    )
    return img


def draw_star(
    size: int, points: int, inner: float, fg: int, bg: int, rot_deg: float
) -> Image.Image:
    """Corner-rich star polygon."""
    R = size * 0.48
    r = R * inner
    ang0 = math.radians(rot_deg)
    verts = []
    for i in range(points * 2):
        a = ang0 + i * math.pi / points
        rad = R if i % 2 == 0 else r
        verts.append((size / 2 + rad * math.cos(a), size / 2 + rad * math.sin(a)))
    img = Image.new("L", (size, size), color=bg)
    d = ImageDraw.Draw(img)
    d.polygon(verts, outline=fg, fill=None, width=max(1, size // 64))
    # add small interior ticks for more corners
    for i in range(points):
        a = ang0 + i * (2 * math.pi / points)
        x0 = size / 2 + r * math.cos(a)
        y0 = size / 2 + r * math.sin(a)
        x1 = size / 2 + (r + size * 0.06) * math.cos(a)
        y1 = size / 2 + (r + size * 0.06) * math.sin(a)
        d.line([x0, y0, x1, y1], fill=fg, width=max(1, size // 64))
    return img


def id_bitmatrix(id_str: str, dim: int = 8) -> np.ndarray:
    bits = np.unpackbits(
        np.frombuffer(hashlib.sha256(id_str.encode()).digest(), dtype=np.uint8)
    )
    m = (bits[: dim * dim] > 0).astype(np.uint8).reshape(dim, dim)
    # Ensure not all zeros/ones
    if m.mean() < 0.2:
        m[0::2, :] = 1
    if m.mean() > 0.8:
        m[1::2, :] = 0
    return m


def draw_bitglyph(
    matrix: np.ndarray, size: int, rot_deg: float, fg: int, bg: int
) -> Image.Image:
    h, w = matrix.shape
    img = Image.new("L", (size, size), color=bg)
    d = ImageDraw.Draw(img)
    step = size / max(h, w)
    for i in range(h):
        for j in range(w):
            if matrix[i, j]:
                x0, y0 = j * step, i * step
                d.rectangle([x0, y0, x0 + step, y0 + step], fill=fg)
    img = img.rotate(rot_deg, resample=Image.BICUBIC, expand=True)
    return img


def value_noise(
    h: int, w: int, rng: np.random.Generator, octaves: int = 4
) -> np.ndarray:
    """Simple multi-octave value noise for nondistinct background texture."""
    base = np.zeros((h, w), np.float32)
    freq = 1
    amp = 1.0
    for _ in range(octaves):
        gh, gw = max(1, h // (8 * freq)), max(1, w // (8 * freq))
        grid = rng.random((gh + 1, gw + 1)).astype(np.float32)
        # Use endpoint=False so floor indices never equal gh/gw.
        y = np.linspace(0, gh, h, endpoint=False, dtype=np.float32)
        x = np.linspace(0, gw, w, endpoint=False, dtype=np.float32)
        yi = np.floor(y).astype(np.int32)
        xi = np.floor(x).astype(np.int32)
        yi1 = np.minimum(yi + 1, gh)
        xi1 = np.minimum(xi + 1, gw)
        dy = y - yi
        dx = x - xi
        # bilinear
        v00 = grid[yi, xi]
        v10 = grid[yi1, xi]
        v01 = grid[yi, xi1]
        v11 = grid[yi1, xi1]
        val = (
            v00 * (1 - dy)[:, None] * (1 - dx)[None, :]
            + v10 * dy[:, None] * (1 - dx)[None, :]
            + v01 * (1 - dy)[:, None] * dx[None, :]
            + v11 * dy[:, None] * dx[None, :]
        )
        base += amp * val
        freq *= 2
        amp *= 0.5
    base -= base.min()
    base /= base.max() + 1e-6
    return base


def hatch_layer(
    img: Image.Image,
    rng: np.random.Generator,
    density: float = 0.004,
    thickness: int = 1,
    angle_deg: float = 30,
):
    d = ImageDraw.Draw(img)
    w, h = img.size
    # draw slanted hatch lines
    spacing = max(6, int(1.0 / math.sqrt(density)))
    length = int(math.hypot(w, h)) + 10
    rad = math.radians(angle_deg)
    dx = math.cos(rad)
    dy = math.sin(rad)
    # start from a negative offset so we cover whole canvas
    for k in range(-length, max(w, h) + length, spacing):
        x0 = k
        y0 = 0
        x1 = k + dx * length
        y1 = dy * length
        d.line([x0, y0, x1, y1], fill=255, width=thickness)


# ----------------------------- layout / anchors -----------------------------


@dc.dataclass
class Anchor:
    name: str
    xy: Tuple[float, float]  # normalized [0,1] creature-space
    size: float  # normalized relative to shorter side


def make_anchors(id_str: str) -> List[Anchor]:
    """Deterministic anchor set covering the canvas, stable per ID."""
    rng = rng_from(id_str)
    anchors: List[Anchor] = []
    # base grid
    for i in range(3):
        for j in range(3):
            x = (j + 0.5) / 3.0
            y = (i + 0.5) / 3.0
            s = 0.18 + 0.06 * rng.random()
            anchors.append(Anchor(name=f"grid_{i}{j}", xy=(x, y), size=s))
    # extra ring anchors on a circle
    R = 0.38
    for k in range(6):
        ang = 2 * math.pi * k / 6 + 0.25 * rng.random()
        x = 0.5 + R * math.cos(ang)
        y = 0.5 + R * math.sin(ang)
        s = 0.14 + 0.05 * rng.random()
        anchors.append(Anchor(name=f"ring_{k}", xy=(x, y), size=s))
    # a central large anchor
    anchors.append(Anchor(name="core", xy=(0.5, 0.5), size=0.28))
    return anchors


# ------------------------------ rendering core ------------------------------


@dc.dataclass
class RenderParams:
    id_str: str
    variant: int
    canvas_size: int
    fg: int = 230
    bg: int = 20
    contrast: float = 1.0
    gamma: float = 1.0
    blur_sigma: float = 0.0
    add_noise: float = 0.0
    occluders: int = 0
    affine: Tuple[float, float, float, float, float, float] = (
        1,
        0,
        0,
        0,
        1,
        0,
    )  # a,b,c,d,e,f PIL matrix


def random_params(id_str: str, variant: int, size: int) -> RenderParams:
    rng = rng_from(id_str, variant)
    # photometric
    contrast = 0.9 + 0.3 * rng.random()
    gamma = 0.8 + 0.5 * rng.random()
    blur_sigma = 0.0 if rng.random() < 0.5 else float(rng.uniform(0.5, 1.8))
    add_noise = float(rng.uniform(0.0, 8.0))
    occluders = int(rng.integers(0, 3))
    # small affine (scale/rotation/shear/translation)
    rot = math.radians(float(rng.uniform(-12, 12)))
    scale = float(rng.uniform(0.92, 1.08))
    shear = math.radians(float(rng.uniform(-5, 5)))
    tx = float(rng.uniform(-0.03, 0.03) * size)
    ty = float(rng.uniform(-0.03, 0.03) * size)
    a = scale * math.cos(rot)
    b = -scale * (math.sin(rot + shear))
    d = scale * math.sin(rot)
    e = scale * math.cos(rot + shear)
    c = tx
    f = ty
    return RenderParams(
        id_str=id_str,
        variant=variant,
        canvas_size=size,
        contrast=contrast,
        gamma=gamma,
        blur_sigma=blur_sigma,
        add_noise=add_noise,
        occluders=occluders,
        affine=(a, b, c, d, e, f),
    )


# --- Cute cartoon base (constant across IDs) --------------------------------


def draw_cartoon_animal(
    size: int,
) -> Tuple[Image.Image, Image.Image, Tuple[int, int, int, int]]:
    """Return (cartoon_rgba, body_mask_L, body_bbox) of a stick-figure animal."""
    W = H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    outline = (10, 10, 10, 255)

    # Body ellipse (mask)
    body_w = int(0.58 * W)
    body_h = int(0.38 * H)
    cx, cy = int(0.52 * W), int(0.58 * H)
    body_bbox = (cx - body_w // 2, cy - body_h // 2, cx + body_w // 2, cy + body_h // 2)
    body_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(body_mask).ellipse(body_bbox, fill=255)

    # Legs
    leg_len = int(0.16 * H)
    leg_xs = [
        int(cx - 0.22 * body_w),
        int(cx - 0.07 * body_w),
        int(cx + 0.07 * body_w),
        int(cx + 0.22 * body_w),
    ]
    y0 = body_bbox[3] - int(0.04 * body_h)
    for x in leg_xs:
        d.line([(x, y0), (x, y0 + leg_len)], fill=outline, width=max(2, size // 256))

    # Head with happy face
    head_r = int(0.12 * W)
    hx, hy = int(0.26 * W), int(0.35 * H)
    head_bb = (hx - head_r, hy - head_r, hx + head_r, hy + head_r)
    d.ellipse(head_bb, outline=outline, width=max(2, size // 256))
    er = max(2, size // 128)
    d.ellipse(
        (hx - head_r // 3 - er, hy - er, hx - head_r // 3 + er, hy + er), fill=outline
    )
    d.ellipse(
        (hx + head_r // 3 - er, hy - er, hx + head_r // 3 + er, hy + er), fill=outline
    )
    sR = int(0.6 * head_r)
    d.arc(
        (hx - sR // 2, hy - sR // 4, hx + sR // 2, hy + sR // 2),
        start=20,
        end=160,
        fill=outline,
        width=max(2, size // 256),
    )

    # Neck & tail
    # d.line([(int(0.42 * W), int(0.48 * H)), (int(0.46 * W), int(0.56 * H))], fill=outline, width=max(2, size // 256))
    tx0, ty0 = body_bbox[2] - int(0.05 * body_w), int(0.52 * H)
    tx1, ty1 = tx0 + int(0.10 * W), ty0 - int(0.08 * H)
    d.line([(tx0, ty0), (tx1, ty1)], fill=outline, width=max(2, size // 256))
    return img, body_mask, body_bbox


# --- Mesh warp: map a rectangular tile into the ellipse ---------------------
def _ellipse_map(
    u: float, v: float, bbox: Tuple[int, int, int, int]
) -> Tuple[float, float]:
    """(u,v) in [0,1]^2 -> point inside ellipse bbox, with slight bulge for 'roundness'."""
    x0, y0, x1, y1 = bbox
    a = (x1 - x0) * 0.5
    b = (y1 - y0) * 0.5
    cx = x0 + a
    cy = y0 + b
    # map to [-1,1]
    X = (u - 0.5) * 2.0
    Y = (v - 0.5) * 2.0
    # gentle spherify to mimic curvature
    r2 = X * X + Y * Y
    bulge = 1.0 - 0.08 * r2
    return cx + a * X * bulge, cy + b * Y * bulge


def warp_pattern_into_ellipse(
    pattern_L: Image.Image,
    body_bbox: Tuple[int, int, int, int],
    canvas_size: Tuple[int, int],
    nx: int = 24,
    ny: int = 18,
) -> Image.Image:
    """Return an L image, same size as canvas, with 'pattern_L' warped into 'body_bbox' ellipse."""
    W, H = canvas_size
    pw, ph = pattern_L.size
    # Mesh: list of (dst_rect, src_quad)
    mesh = []
    for iy in range(ny):
        v0 = iy / ny
        v1 = (iy + 1) / ny
        sy0 = int(round(v0 * ph))
        sy1 = int(round(v1 * ph))
        for ix in range(nx):
            u0 = ix / nx
            u1 = (ix + 1) / nx
            sx0 = int(round(u0 * pw))
            sx1 = int(round(u1 * pw))
            # destination quad (clockwise) in canvas coords
            x00, y00 = _ellipse_map(u0, v0, body_bbox)
            x10, y10 = _ellipse_map(u1, v0, body_bbox)
            x11, y11 = _ellipse_map(u1, v1, body_bbox)
            x01, y01 = _ellipse_map(u0, v1, body_bbox)
            dst_rect = (
                int(min(x00, x10, x11, x01)),
                int(min(y00, y10, y11, y01)),
                int(max(x00, x10, x11, x01)),
                int(max(y00, y10, y11, y01)),
            )
            src_quad = (sx0, sy0, sx1, sy0, sx1, sy1, sx0, sy1)
            mesh.append((dst_rect, src_quad))
    # carrier = Image.new("L", (W, H), 255)  # start white; mesh transform writes in
    # warped = carrier.transform(
    #     size=(W, H),
    #     method=Image.MESH,
    #     data=mesh,
    #     resample=Image.BICUBIC,
    #     fill=255
    # )

    # Perform warp directly on the pattern itself
    warped = pattern_L.transform(
        (W, H), Image.MESH, mesh, resample=Image.BICUBIC, fill=255
    )

    # Mask strictly to the ellipse to remove blocky corners
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse(body_bbox, fill=255)
    warped = Image.composite(warped, Image.new("L", (W, H), 255), mask)
    return warped


# --- Distinctive pattern layer (derived from ID) -----------------------------


def render_id_pattern_layer(
    params: RenderParams, out_size: Tuple[int, int]
) -> Image.Image:
    """
    High-contrast, SIFT-friendly pattern (L) sized to out_size.
    Simplified: checkers + bit-glyphs + sparse bullseyes. Black on white.
    """
    W, H = out_size
    fg, bg = 0, 255  # strong contrast: black ink on white paper
    canvas = Image.new("L", (W, H), color=bg)
    anchors = make_anchors(params.id_str)
    M = id_bitmatrix(params.id_str, dim=8)

    for idx, anchor in enumerate(anchors):
        cx = int(anchor.xy[0] * W)
        cy = int(anchor.xy[1] * H)
        s = int(anchor.size * min(W, H))
        if s < 8:
            continue
        if idx % 3 == 0:
            rot = seed_from_string(params.id_str + anchor.name) % 360
            glyph = draw_bitglyph(M, s, rot, fg, bg)
        elif idx % 3 == 1:
            rot = seed_from_string(anchor.name + params.id_str) % 360
            glyph, pos = draw_checker(
                ImageDraw.Draw(canvas), cx, cy, s, tiles=5, rot=rot, fg=fg, bg=bg
            )
            canvas.paste(glyph, pos, glyph)
            continue
        else:
            glyph = draw_bullseye(size=s, rings=6, fg=fg, bg=bg)
        x = int(cx - glyph.width // 2)
        y = int(cy - glyph.height // 2)
        canvas.paste(glyph, (x, y), glyph)
    return canvas


def compose_creature_body_pattern(
    params: RenderParams, debug: bool = False
) -> Tuple[Image.Image, Dict]:
    """Compose white background + cute cartoon + **mesh-warp** ID pattern into the body ellipse."""
    size = params.canvas_size
    W = H = size

    # White background for clarity (less wash-out)
    base = Image.new("L", (W, H), 255)

    # Cartoon & mask
    cartoon_rgba, body_mask, body_bbox = draw_cartoon_animal(size)

    # Distinctive pattern and real warp into ellipse
    bw = body_bbox[2] - body_bbox[0]
    bh = body_bbox[3] - body_bbox[1]

    # raw_pattern = render_id_pattern_layer(params, (bw, bh))  # black on white
    # warped = warp_pattern_into_ellipse(raw_pattern, body_bbox, (W, H), nx=28, ny=22)
    # # Clip strictly to ellipse and darken a touch for punch
    # body_layer = ImageChops.multiply(warped, ImageOps.invert(body_mask))
    # body_layer = ImageChops.invert(body_layer)  # back to black-on-white in ellipse only
    # creature = ImageChops.multiply(base, body_layer)

    raw_pattern = render_id_pattern_layer(params, (bw, bh))  # black on white
    warped = warp_pattern_into_ellipse(raw_pattern, body_bbox, (W, H), nx=20, ny=16)
    # Pattern is already white outside the ellipse; place it on the white base
    creature = ImageChops.multiply(base, warped)  # (equivalent to just `warped`)

    # Photometric tweaks
    creature = ImageEnhance.Contrast(creature).enhance(params.contrast)
    if params.blur_sigma > 0:
        creature = creature.filter(ImageFilter.GaussianBlur(radius=params.blur_sigma))
    if params.add_noise > 0:
        arr = np.array(creature, dtype=np.float32)
        arr += np.random.default_rng(
            seed_from_string(params.id_str) ^ params.variant
        ).normal(0, params.add_noise, arr.shape)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        creature = Image.fromarray(arr, mode="L")

    # Overlay cartoon outlines on top for cuteness/consistency
    tmp = Image.new("RGB", (W, H), (255, 255, 255))
    tmp.paste(cartoon_rgba, mask=cartoon_rgba.split()[-1])
    lines = ImageOps.grayscale(tmp)
    creature = ImageChops.darker(creature, lines)

    # # Overlay cartoon outlines on top for cuteness/consistency
    # outlines = ImageOps.invert(Image.new("L", (W, H), 255))
    # # Convert cartoon to pure edges (keep RGBA outlines as dark on white)
    # edges = Image.new("L", (W, H), 0)
    # edges_rgba = cartoon_rgba
    # # Composite edges by drawing the RGBA onto a blank white then edge-detect via min
    # tmp = Image.new("RGB", (W, H), (255, 255, 255))
    # tmp.paste(edges_rgba, mask=edges_rgba.split()[-1])
    # # Convert lines to grayscale and darken
    # lines = ImageOps.grayscale(tmp)
    # lines = ImageOps.autocontrast(lines)
    # creature = ImageChops.darker(creature, lines)

    meta = {
        "id": params.id_str,
        "variant": params.variant,
        "body_bbox": body_bbox,
        "contrast": params.contrast,
        "gamma": params.gamma,
        "blur_sigma": params.blur_sigma,
        "add_noise": params.add_noise,
    }

    if debug and cv2 is not None:
        overlay = np.array(creature.convert("RGB"))
        gray = np.array(creature)
        kps = []
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

    return creature, meta


# --------------------------------- dataset ----------------------------------


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


# ---------------------------------- CLI -------------------------------------


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
        # Permute anchor layout globally (still deterministic) for diversity
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
    main()
