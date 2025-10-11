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
    """
    Draw a star outline with inner rays.

    CommandLine:
        xdoctest -m ibeis.demo.primitives draw_star --show

    Example:
        >>> import numpy as np
        >>> from ibeis.demo.primitives import draw_star
        >>> img = draw_star(size=256, points=7, inner=0.45, fg=0, bg=255, rot_deg=12)
        >>> arr = np.asarray(img)
        >>> assert img.mode == 'L' and img.size == (256, 256)
        >>> assert (arr < 255).any()
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl()
        >>> kwplot.imshow(arr, doclf=True, title='draw_star')
        >>> kwplot.show_if_requested()

    Example:
        >>> # Grid: points / inner / rotation sweep
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.primitives import draw_star
        >>> points_list = [5, 8]
        >>> inner_list  = [0.35, 0.45, 0.55]
        >>> rot_list    = [0]
        >>> canvases = []
        >>> for p in points_list:
        ...     for inner in inner_list:
        ...         for r in rot_list:
        ...             im = draw_star(160, p, inner, fg=0, bg=255, rot_deg=r)
        ...             rgb = kwimage.atleast_3channels(np.asarray(im))
        ...             rgb = kwimage.draw_header_text(rgb, f'p={p}, i={inner:.2f}, r={r}')
        ...             canvases.append(rgb)
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=len(rot_list), pad=6, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='draw_star grid'); kwplot.show_if_requested()
    """
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
    """
    Generate a deterministic bit matrix from an id string.

    CommandLine:
        xdoctest -m ibeis.demo.primitives id_bitmatrix

    Example:
        >>> import numpy as np
        >>> from ibeis.demo.primitives import id_bitmatrix
        >>> m = id_bitmatrix('demo-id', dim=8)
        >>> assert m.shape == (8, 8) and m.dtype == np.uint8
        >>> assert set(np.unique(m)).issubset({0, 1})
        >>> # Deterministic repeatability
        >>> assert np.array_equal(m, id_bitmatrix('demo-id', dim=8))

    Example:
        >>> # Different dims; visualize as a tiny sprite sheet
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.primitives import id_bitmatrix
        >>> dims = [6, 8, 10, 12]
        >>> canvases = []
        >>> for d in dims:
        ...     m = id_bitmatrix('demo-id', dim=d) * 255
        ...     # nearest resize so the blocks stay crisp
        ...     sprite = kwimage.imresize(m, dsize=(d*12, d*12), interpolation='nearest')
        ...     rgb = kwimage.atleast_3channels(sprite.astype(np.uint8))
        ...     rgb = kwimage.draw_header_text(rgb, f'dim={d}')
        ...     canvases.append(rgb)
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=2, pad=6, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='id_bitmatrix dims'); kwplot.show_if_requested()
    """
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
    """
    Render a binary matrix as a pixel glyph, optionally rotated.

    CommandLine:
        xdoctest -m ibeis.demo.primitives draw_bitglyph --show

    Example:
        >>> import numpy as np
        >>> from ibeis.demo.primitives import id_bitmatrix, draw_bitglyph
        >>> m = id_bitmatrix('glyph-id', dim=8)
        >>> img = draw_bitglyph(m, size=256, rot_deg=30, fg=0, bg=255)
        >>> arr = np.asarray(img)
        >>> assert (arr < 255).any()
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(arr, doclf=True, title='draw_bitglyph'); kwplot.show_if_requested()

    Example:
        >>> # Grid: rotate several glyphs of different sizes
        >>> import numpy as np, kwimage
        >>> from ibeis.demo.primitives import id_bitmatrix, draw_bitglyph
        >>> sizes = [96, 128, 160]
        >>> rots  = [0, 15, 30, 45]
        >>> canvases = []
        >>> for s in sizes:
        ...     m = id_bitmatrix(f'glyph-{s}', dim=8)
        ...     for r in rots:
        ...         im = draw_bitglyph(m, size=s, rot_deg=r, fg=0, bg=255)
        ...         rgb = kwimage.atleast_3channels(np.asarray(im))
        ...         rgb = kwimage.draw_header_text(rgb, f's={s}, r={r}')
        ...         canvases.append(rgb)
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=len(rots), pad=6, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='draw_bitglyph grid'); kwplot.show_if_requested()
    """
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
    """
    Draw a slanted line hatch on an L image, in-place.

    CommandLine:
        xdoctest -m ibeis.demo.primitives hatch_layer --show

    Example:
        >>> import numpy as np
        >>> from numpy.random import default_rng
        >>> from PIL import Image
        >>> from ibeis.demo.primitives import hatch_layer
        >>> canvas = Image.new('L', (256, 256), 0)
        >>> before = np.asarray(canvas).sum()
        >>> hatch_layer(canvas, rng=default_rng(0), density=0.01, thickness=2, angle_deg=30)
        >>> after = np.asarray(canvas).sum()
        >>> assert after > before
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(canvas, title='hatch_layer'); kwplot.show_if_requested()

    Example:
        >>> # Grid: density / thickness / angle sweep
        >>> import numpy as np, kwimage
        >>> from numpy.random import default_rng
        >>> from PIL import Image
        >>> from ibeis.demo.primitives import hatch_layer
        >>> dens = [0.004, 0.008, 0.016]
        >>> thks = [1, 2]
        >>> angs = [15, 45, 75]
        >>> canvases = []
        >>> for d in dens:
        ...     for t in thks:
        ...         for a in angs:
        ...             base = Image.new('L', (180, 180), 0)
        ...             hatch_layer(base, rng=default_rng(0), density=d, thickness=t, angle_deg=a)
        ...             rgb = kwimage.atleast_3channels(np.asarray(base))
        ...             rgb = kwimage.draw_header_text(rgb, f'd={d}, t={t}, a={a}')
        ...             canvases.append(rgb)
        >>> grid = kwimage.stack_images_grid(canvases, chunksize=len(angs), pad=6, bg_value='kitware_gray')
        >>> # xdoctest: +REQUIRES(--show)
        >>> import kwplot; kwplot.autompl(); kwplot.imshow(grid, title='hatch_layer grid'); kwplot.show_if_requested()
    """
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
