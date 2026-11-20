import math

import numpy as np

NAME = "sand_dunes"
DURATION = 60
FPS = 20

SUN_PERIOD = 60.0


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return {"x": x, "y": y}


def render(state, t):
    x, y = state["x"], state["y"]
    cx, cy = 32.0, 32.0

    a = 2 * math.pi * t / SUN_PERIOD
    sun_x = 32.0 + 28.0 * math.cos(a)
    sun_y = 12.0 + 24.0 * math.sin(a)
    dx = x - sun_x
    dy = y - sun_y
    r2 = dx * dx + dy * dy
    r = np.sqrt(r2 + 1e-6)

    # Dune surface: several sinusoidal ridges, static
    dune = (
        10.0 * np.sin(x * 0.14 + 1.3)
        + 8.0 * np.sin(y * 0.18 + 0.5)
        + 6.0 * np.sin((x + y) * 0.11 + 2.1)
        + 4.0 * np.sin((x - y) * 0.15)
    )

    # Light from sun direction, Lambert-like: higher dune parts facing sun lit
    lx = -dx / r
    ly = -dy / r
    # Approximate surface normal perturbation by dune gradients
    gx = 1.0 * (
        10.0 * 0.14 * np.cos(x * 0.14 + 1.3)
        + 8.0 * 0.0 * np.cos(y * 0.18 + 0.5)
        + 6.0 * 0.11 * np.cos((x + y) * 0.11 + 2.1)
        + 4.0 * 0.15 * np.cos((x - y) * 0.15)
    )
    gy = 1.0 * (
        10.0 * 0.0 * np.cos(x * 0.14 + 1.3)
        + 8.0 * 0.18 * np.cos(y * 0.18 + 0.5)
        + 6.0 * 0.11 * np.cos((x + y) * 0.11 + 2.1)
        + 4.0 * (-0.15) * np.cos((x - y) * 0.15)
    )
    nz = 1.0
    # normal
    nx = -gx
    ny = -gy
    nn = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx = nx / nn
    ny = ny / nn
    nz = nz / nn

    # lambert: dot(n, L) where L = (lx, ly, 0.4) normalized-ish
    Lx, Ly, Lz = lx * 0.7, ly * 0.7, 0.7
    ln = np.sqrt(Lx * Lx + Ly * Ly + Lz * Lz)
    Lx, Ly, Lz = Lx / ln, Ly / ln, Lz / ln

    lam = np.clip(nx * Lx + ny * Ly + nz * Lz, 0.0, 1.0)

    # shadow: where the sun is below horizon, or dune occludes
    shadow = np.clip(1.0 - lam * 1.6, 0.0, 1.0)  # 0 lit, 1 shadow
    # also fade shadow when sun is far (higher in sky = less shadow)
    sun_height = 0.5 - 0.5 * math.sin(a)  # when sin(a) is -1 (bottom) sun low
    shadow *= 0.4 + 0.6 * sun_height

    # sand color: warm sandy
    base_r, base_g, base_b = 230.0, 185.0, 120.0
    # darker in shadow, slightly cooler
    lit_r = base_r * lam + 30.0 * (1.0 - lam)
    lit_g = base_g * lam + 25.0 * (1.0 - lam)
    lit_b = base_b * lam + 40.0 * (1.0 - lam)

    # subtle dune relief tint
    tint = (dune + 28.0) / 56.0  # 0..1
    lit_r *= 0.85 + 0.15 * tint
    lit_g *= 0.85 + 0.15 * tint
    lit_b *= 0.85 + 0.15 * tint

    # apply shadow darkening
    lit_r *= 1.0 - 0.75 * shadow
    lit_g *= 1.0 - 0.75 * shadow
    lit_b *= 1.0 - 0.65 * shadow

    rgb = np.stack([lit_r, lit_g, lit_b], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)
