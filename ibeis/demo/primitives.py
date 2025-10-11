from __future__ import annotations
import math
import numpy as np
from PIL import Image, ImageDraw


def draw_spiral(
    size: int, turns: float, stroke: int, fg: int, bg: int, rot_deg: float = 0
) -> Image.Image:
    """
    Example:
        >>> import numpy as np
        >>> from ibeis.demo.primitives import draw_spiral
        >>> size = 256
        >>> img = draw_spiral(size=size, turns=2.0, stroke=3, fg=0, bg=255, rot_deg=15)
        >>> assert img.mode == 'L' and img.size == (size, size)
        >>> arr = np.array(img)
        >>> assert arr.mean() < 255  # not a blank canvas
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(arr, fnum=1, doclf=True, title='draw_spiral')
        >>> kwplot.show_if_requested()
    """
    img = Image.new("L", (size, size), color=bg)
    d = ImageDraw.Draw(img)
    cx = cy = size / 2
    R = size * 0.45
    steps = max(300, int(600 * turns))
    pts = []
    for i in range(steps):
        t = i / (steps - 1)
        ang = (rot_deg * math.pi / 180.0) + t * turns * 2 * math.pi
        r = t * R
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.line(pts, fill=fg, width=stroke)
    return img


def draw_bezier_stripes(
    size: int, stripes: int, stroke: int, fg: int, bg: int, rng: np.random.Generator
) -> Image.Image:
    """
    Example:
        >>> import numpy as np
        >>> from numpy.random import default_rng
        >>> from ibeis.demo.primitives import draw_bezier_stripes
        >>> rng = default_rng(0)
        >>> img = draw_bezier_stripes(size=256, stripes=4, stroke=3, fg=0, bg=255, rng=rng)
        >>> arr = np.array(img)
        >>> assert arr.shape == (256, 256) and arr.dtype == np.uint8
        >>> assert (arr < 250).sum() > 0  # should have dark inked pixels
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(arr, fnum=1, doclf=True, title='draw_bezier_stripes')
        >>> kwplot.show_if_requested()
    """
    img = Image.new("L", (size, size), color=bg)
    d = ImageDraw.Draw(img)
    for _ in range(stripes):
        P0 = (rng.uniform(0.0, 0.2) * size, rng.uniform(0.2, 0.8) * size)
        P3 = (rng.uniform(0.8, 1.0) * size, rng.uniform(0.2, 0.8) * size)
        P1 = (rng.uniform(0.2, 0.5) * size, rng.uniform(0.0, 1.0) * size)
        P2 = (rng.uniform(0.5, 0.8) * size, rng.uniform(0.0, 1.0) * size)
        pts = []
        for i in range(120):
            t = i / 119.0
            mt = 1 - t
            x = (
                (mt**3) * P0[0]
                + 3 * (mt**2) * t * P1[0]
                + 3 * mt * (t**2) * P2[0]
                + (t**3) * P3[0]
            )
            y = (
                (mt**3) * P0[1]
                + 3 * (mt**2) * t * P1[1]
                + 3 * mt * (t**2) * P2[1]
                + (t**3) * P3[1]
            )
            pts.append((x, y))
        d.line(pts, fill=fg, width=stroke)
    return img


def draw_checker(draw: ImageDraw.ImageDraw, cx, cy, size, tiles, rot, fg, bg):
    """
    CommandLine:
        xdoctest -m ibeis.demo.primitives draw_checker --show

    Example:
        >>> import numpy as np
        >>> from PIL import Image, ImageDraw, ImageOps
        >>> from ibeis.demo.primitives import draw_checker
        >>> # The first arg is only type-hinted; it isn't used internally.
        >>> dummy_draw = ImageDraw.Draw(Image.new('L', (1, 1)))
        >>> tile, (x, y) = draw_checker(dummy_draw, cx=128, cy=128, size=150,
        ...                             tiles=6, rot=25, fg=0, bg=255)
        >>> base = Image.new('L', (256, 256), 255)
        >>> # Paste using the inverted tile as a mask (ink = black)
        >>> base.paste(Image.new('L', tile.size, 0), (x, y), ImageOps.invert(tile))
        >>> arr = np.array(base)
        >>> assert arr.shape == (256, 256) and (arr < 255).any()
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(arr, fnum=1, doclf=True, title='draw_checker (pasted)')
        >>> kwplot.show_if_requested()
    """
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
    """
    CommandLine:
        xdoctest -m ibeis.demo.primitives draw_bullseye --show

    Example:
        >>> import numpy as np
        >>> from ibeis.demo.primitives import draw_bullseye
        >>> img = draw_bullseye(size=256, rings=10, fg=0, bg=255)
        >>> arr = np.array(img)
        >>> assert arr.min() == 0 or arr.max() == 255
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot
        >>> kwplot.autompl()
        >>> kwplot.imshow(arr, fnum=1, doclf=True, title='draw_bullseye')
        >>> kwplot.show_if_requested()
    """
    img = Image.new("L", (size, size), color=bg)
    d = ImageDraw.Draw(img)
    for k in range(rings):
        r = size * (0.5 - 0.45 * (k / rings))
        bbox = [size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r]
        col = fg if k % 2 == 0 else bg
        d.ellipse(bbox, outline=col, width=max(1, size // 64))
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
    for i in range(points):
        a = ang0 + i * (2 * math.pi / points)
        x0 = size / 2 + r * math.cos(a)
        y0 = size / 2 + r * math.sin(a)
        x1 = size / 2 + (r + size * 0.06) * math.cos(a)
        y1 = size / 2 + (r + size * 0.06) * math.sin(a)
        d.line([x0, y0, x1, y1], fill=fg, width=max(1, size // 64))
    return img


def id_bitmatrix(id_str: str, dim: int = 8) -> np.ndarray:
    import hashlib
    import numpy as np

    bits = np.unpackbits(
        np.frombuffer(hashlib.sha256(id_str.encode()).digest(), dtype=np.uint8)
    )
    m = (bits[: dim * dim] > 0).astype(np.uint8).reshape(dim, dim)
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


def hatch_layer(
    img, rng, density: float = 0.004, thickness: int = 1, angle_deg: float = 30
):
    d = ImageDraw.Draw(img)
    w, h = img.size
    spacing = max(6, int(1.0 / math.sqrt(density)))
    length = int(math.hypot(w, h)) + 10
    rad = math.radians(angle_deg)
    dx = math.cos(rad)
    dy = math.sin(rad)
    for k in range(-length, max(w, h) + length, spacing):
        x0 = k
        y0 = 0
        x1 = k + dx * length
        y1 = dy * length
        d.line([x0, y0, x1, y1], fill=255, width=thickness)
