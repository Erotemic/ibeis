from __future__ import annotations
import dataclasses as dc
import math
from typing import Tuple, List
import kwarray
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from ibeis.demo.utils import rng_from, seed_from_string, id_to_colors  # NOQA
from ibeis.demo.primitives import (
    draw_bitglyph,
    draw_checker,
    draw_star,
    draw_spiral,
    draw_bezier_stripes,
)


@dc.dataclass
class Anchor:
    name: str
    xy: Tuple[float, float]  # normalized [0,1] in body-space
    size: float  # relative to shorter side


def make_anchors(rng=None) -> List[Anchor]:
    """
    Generate deterministic anchors with a small, variant-dependent jitter so
    different variants remain coherent but not identical.

    Example:
        >>> from ibeis.demo.pattern import *  # NOQA
        >>> anchors = make_anchors(0)
        >>> import ubelt as ub
        >>> print(f'anchors = {ub.urepr(anchors, nl=1)}')

    """
    rng = kwarray.ensure_rng(rng)
    anchors: List[Anchor] = []
    for i in range(3):
        for j in range(3):
            # x = (j + 0.5) / 3.0
            # y = (i + 0.5) / 3.0
            # s = 0.18 + 0.06 * rng.random()
            # small position/size jitter per variant
            x = (j + 0.5) / 3.0 + float(rng.uniform(-0.02, 0.02))
            y = (i + 0.5) / 3.0 + float(rng.uniform(-0.02, 0.02))
            s = 0.18 + 0.06 * float(rng.random())
            anchors.append(Anchor(name=f"grid_{i}{j}", xy=(x, y), size=s))
    R = 0.38
    for k in range(6):
        ang = 2 * math.pi * k / 6 + 0.25 * rng.random()
        x = 0.5 + R * math.cos(ang)
        y = 0.5 + R * math.sin(ang)
        # s = 0.14 + 0.05 * rng.random()
        s = 0.14 + 0.05 * float(rng.random())
        anchors.append(Anchor(name=f"ring_{k}", xy=(x, y), size=s))
    anchors.append(Anchor(name="core", xy=(0.5, 0.5), size=0.28))
    return anchors


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


def random_params(id_str: str, variant: int, size: int) -> RenderParams:
    rng = rng_from(id_str, variant)
    contrast = 0.9 + 0.3 * rng.random()
    gamma = 0.8 + 0.5 * rng.random()
    blur_sigma = 0.0 if rng.random() < 0.5 else float(rng.uniform(0.5, 1.8))
    add_noise = float(rng.uniform(0.0, 8.0))
    occluders = int(rng.integers(0, 3))
    # occluders = 0
    return RenderParams(
        id_str,
        variant,
        size,
        contrast=contrast,
        gamma=gamma,
        blur_sigma=blur_sigma,
        add_noise=add_noise,
        occluders=occluders,
    )


def render_id_pattern_layer(
    params: RenderParams, out_size: Tuple[int, int]
) -> Image.Image:
    """
    Produce an RGB raster (white background) in body-space of size out_size,
    filled with high-contrast, SIFT-friendly structures, deterministically keyed by id_str.

    CommandLine:
        xdoctest -m ibeis.demo.pattern render_id_pattern_layer --show

    Example:
        >>> from ibeis.demo.pattern import RenderParams, render_id_pattern_layer
        >>> params = RenderParams('zebra-demo', 0, 256)
        >>> img = render_id_pattern_layer(params, (256, 256))
        >>> assert img.mode == 'RGB' and img.size == (256, 256)
        >>> import numpy as np
        >>> arr = np.array(img)
        >>> assert (arr != 255).any()  # should not be blank
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(arr, fnum=1, doclf=True, title='render_id_pattern_layer')
        >>> kwplot.show_if_requested()

    Example:
        >>> # Grid of variations across multiple IDs / variants (visual check)
        >>> from ibeis.demo.pattern import *  # NOQA
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.pattern import RenderParams, render_id_pattern_layer
        >>> ids = ['zebra-001', 'zebra-002', 'zebra-003']
        >>> vars = [0, 1, 2]
        >>> canvases = []
        >>> for name in ids:
        ...     for v in vars:
        ...         p = RenderParams(name, v, 192)
        ...         im = render_id_pattern_layer(p, (192, 192))
        ...         rgb = kwimage.ensure_float01(np.array(im))
        ...         rgb = kwimage.draw_header_text(rgb, f'{name} v{v}')
        ...         canvases.append((rgb * 255).astype(np.uint8))
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=len(vars), pad=6, bg_value='kitware_gray')
        >>> assert grid.ndim == 3
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(grid, fnum=1, doclf=True, title='render_id_pattern_layer grid')
        >>> kwplot.show_if_requested()
    """
    W, H = out_size
    # Do colors later
    # fg_rgb, accent_rgb = id_to_colors(params.id_str)
    fg_rgb = (0, 0, 0)
    accent_rgb = (50, 50, 50)
    canvas = Image.new("RGB", (W, H), color=(255, 255, 255))

    id_rng = kwarray.ensure_rng(params.id_str)
    variant_rng = kwarray.ensure_rng(params.id_str + str(params.variant))
    anchors = make_anchors(rng=id_rng)

    # precompute bitmatrix only if needed
    bm = None

    for idx, anchor in enumerate(anchors):
        cx = int(anchor.xy[0] * W)
        cy = int(anchor.xy[1] * H)
        s = int(anchor.size * min(W, H))
        if s < 10:  # too small to matter
            continue
        choice = id_rng.randint(0, 5)
        # rotate glyph family by variant so variants look different yet consistent
        # choice = (idx + int(params.variant)) % 5
        if choice == 0:
            from ibeis.demo.primitives import id_bitmatrix
            if bm is None:
                bm = id_bitmatrix(params.id_str, dim=8)
            rot = id_rng.rand() * 360
            gL = draw_bitglyph(bm, s, rot, fg=0, bg=255)
        elif choice == 1:
            rot = id_rng.rand() * 360
            gL, _ = draw_checker(
                ImageDraw.Draw(Image.new("L", (1, 1))),
                0,
                0,
                s,
                tiles=5,
                rot=rot,
                fg=0,
                bg=255,
            )
            x = int(cx - gL.width // 2)
            y = int(cy - gL.height // 2)
            mask = ImageOps.invert(gL)
            tile = Image.new("RGB", gL.size, fg_rgb)
            canvas.paste(tile, (x, y), mask)
            continue
        elif choice == 2:
            gL = draw_star(
                size=s,
                points=7,
                inner=0.45,
                fg=0,
                bg=255,
                rot_deg=(seed_from_string("star" + params.id_str + anchor.name) % 360),
            )
        elif choice == 3:
            gL = draw_spiral(
                size=s,
                turns=1.8,
                stroke=max(2, s // 40),
                fg=0,
                bg=255,
                rot_deg=(seed_from_string("spi" + anchor.name) % 360),
            )
        else:
            gL = draw_bezier_stripes(
                size=s, stripes=3, stroke=max(2, s // 36), fg=0, bg=255,
                rng=id_rng
            )

        x = int(cx - gL.width // 2)
        y = int(cy - gL.height // 2)
        mask = ImageOps.invert(gL)  # 255 where ink
        tile = Image.new("RGB", gL.size, fg_rgb)
        canvas.paste(tile, (x, y), mask)

        outline = Image.new("RGB", gL.size, accent_rgb)
        thin = gL.filter(ImageFilter.MaxFilter(size=3))  # slight dilate
        canvas.paste(outline, (x, y), ImageOps.invert(thin))

    # Optional: apply a tiny global affine jitter so variants are perceptibly unique.
    # Keeps structure recognizable for matching while changing appearance.
    if 0:
        try:
            # nudge with small scale/shear/translate
            sx = 1.0 + float(variant_rng.uniform(-0.035, 0.035))
            sy = 1.0 + float(variant_rng.uniform(-0.035, 0.035))
            shx = float(variant_rng.uniform(-0.028, 0.028))
            shy = float(variant_rng.uniform(-0.028, 0.028))
            tx = float(variant_rng.uniform(-0.02, 0.02)) * W
            ty = float(variant_rng.uniform(-0.02, 0.02)) * H
            A = (sx, shx, tx,  shy, sy,  ty)
            canvas = canvas.transform(canvas.size, Image.AFFINE, A, resample=Image.BICUBIC)
        except Exception:
            # Be conservative: if anything goes wrong, just return the unwarped canvas.
            pass
    return canvas
