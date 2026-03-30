from __future__ import annotations
import hashlib
from typing import Tuple
import numpy as np
from PIL import Image, ImageOps


# ---- seeds / rng ----
def seed_from_string(s: str) -> int:
    h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big", signed=False)


def rng_from(s: str, extra: int = 0) -> np.random.Generator:
    seed = seed_from_string(s) ^ (extra * 0x9E3779B185EBCA87)
    return np.random.default_rng(seed & ((1 << 63) - 1))


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


# ---- color helpers ----
def id_to_colors(id_str: str) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    h = seed_from_string(id_str) % 360
    S, V = 0.75, 0.95
    c = V * S
    X = c * (1 - abs((h / 60) % 2 - 1))
    m = V - c
    sextant = h // 60
    if sextant == 0:
        r, g, b = c, X, 0
    elif sextant == 1:
        r, g, b = X, c, 0
    elif sextant == 2:
        r, g, b = 0, c, X
    elif sextant == 3:
        r, g, b = 0, X, c
    elif sextant == 4:
        r, g, b = X, 0, c
    else:
        r, g, b = c, 0, X
    rgb = (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))
    accent = tuple(max(0, int(v * 0.55)) for v in rgb)
    return rgb, accent


def id_to_color_pair(id_str: str) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    def hsv_to_rgb(h: int, S: float = 0.78, V: float = 0.96):
        c = V * S
        X = c * (1 - abs((h / 60) % 2 - 1))
        m = V - c
        sextant = h // 60
        if sextant == 0:
            r, g, b = c, X, 0
        elif sextant == 1:
            r, g, b = X, c, 0
        elif sextant == 2:
            r, g, b = 0, c, X
        elif sextant == 3:
            r, g, b = 0, X, c
        elif sextant == 4:
            r, g, b = X, 0, c
        else:
            r, g, b = c, 0, X
        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))

    h0 = seed_from_string(id_str) % 360
    return hsv_to_rgb(h0), hsv_to_rgb((h0 + 160) % 360)


# ---- gradients / noise ----
def diagonal_gradient(size: Tuple[int, int], color1, color2, angle_deg: float = 45.0):
    W, H = size
    L = max(W, H)
    g = Image.linear_gradient("L").resize((L, L))
    g = g.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
    left = (g.width - W) // 2
    top = (g.height - H) // 2
    g = g.crop((left, top, left + W, top + H))
    return ImageOps.colorize(g, black=color1, white=color2)


def value_noise(h: int, w: int, rng: np.random.Generator, octaves: int = 4) -> np.ndarray:
    base = np.zeros((h, w), np.float32)
    freq, amp = 1, 1.0
    for _ in range(octaves):
        gh, gw = max(1, h // (8 * freq)), max(1, w // (8 * freq))
        grid = rng.random((gh + 1, gw + 1)).astype(np.float32)
        y = np.linspace(0, gh, h, endpoint=False, dtype=np.float32)
        x = np.linspace(0, gw, w, endpoint=False, dtype=np.float32)
        yi = np.floor(y).astype(np.int32)
        xi = np.floor(x).astype(np.int32)
        yi1 = np.minimum(yi + 1, gh)
        xi1 = np.minimum(xi + 1, gw)
        dy = y - yi
        dx = x - xi

        # ✅ FIXED: use broadcasted (outer) indexing
        yi_ = yi[:, None]
        yi1_ = yi1[:, None]
        xi_ = xi[None, :]
        xi1_ = xi1[None, :]

        v00 = grid[yi_, xi_]
        v10 = grid[yi1_, xi_]
        v01 = grid[yi_, xi1_]
        v11 = grid[yi1_, xi1_]

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
