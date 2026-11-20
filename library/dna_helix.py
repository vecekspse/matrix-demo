"""DNA double helix rotating on a 64x64 RGB LED matrix.

Two saturated strands wind around the vertical axis, rotating around Y.
Base pairs (rungs) are drawn as horizontal lines between the strands at
regular Y intervals. Colors: strand A = red/magenta, strand B = cyan/green.
Dark background. Period 10 s divides DURATION (30 s) for a seamless loop.
"""
import math

import numpy as np

NAME = "dna_helix"
DURATION = 30
FPS = 20

PERIOD = 10.0
NUM_RUNGS = 16
RADIAL_SPREAD = 22.0
AMPLITUDE_Y = 24.0


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # center the grid
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    # normalized coords in range roughly -1..1
    nx = (x - cx) / cx
    ny = (y - cy) / cy
    return {
        "x": x, "y": y, "nx": nx, "ny": ny,
        "cx": cx, "cy": cy,
    }


def render(state, t):
    x, y = state["x"], state["y"]
    nx, ny = state["nx"], state["ny"]
    H, W = x.shape

    phase = 2.0 * math.pi * t / PERIOD

    # Precompute the helix strands as parametric curves.
    # Strand A: angle = phase + u * 2pi * K
    # Strand B: angle = phase + u * 2pi * K + pi
    # u in [0,1] maps to vertical position from top to bottom.

    # We'll evaluate the helix at many points and accumulate into buffers.
    # Use a small loop over ~80 points per strand (2 strands = 160 points total),
    # which is within the "small number of objects" allowance.

    N_PER_STRAND = 80
    u = np.linspace(0.0, 1.0, N_PER_STRAND)
    # vertical position: map u to y in pixel coords, with some margin
    y_top = 4.0
    y_bot = H - 5.0
    y_pos = y_top + u * (y_bot - y_top)

    # helix radius in x
    r = RADIAL_SPREAD

    # Number of full turns over the visible height
    TURNS = 2.0

    # Strand A
    angle_a = phase + u * TURNS * 2.0 * math.pi
    xa = state["cx"] + r * np.sin(angle_a)
    ya = y_pos

    # Strand B (offset by pi)
    angle_b = phase + u * TURNS * 2.0 * math.pi + math.pi
    xb = state["cx"] + r * np.sin(angle_b)
    yb = y_pos

    # Depth for shading: cos of angle gives z (positive = front)
    za = np.cos(angle_a)
    zb = np.cos(angle_b)

    # Accumulate RGB
    rgb = np.zeros((H, W, 3), dtype=np.float32)

    # Draw strand A (red/magenta)
    for i in range(N_PER_STRAND):
        px = int(round(xa[i]))
        py = int(round(ya[i]))
        if 0 <= px < W and 0 <= py < H:
            # shade by depth: brighter in front
            depth = max(0.3, (za[i] + 1) / 2.0)
            rgb[py, px, 0] = 220.0 * depth
            rgb[py, px, 1] = 30.0 * depth
            rgb[py, px, 2] = 120.0 * depth

    # Draw strand B (cyan)
    for i in range(N_PER_STRAND):
        px = int(round(xb[i]))
        py = int(round(yb[i]))
        if 0 <= px < W and 0 <= py < H:
            depth = max(0.3, (zb[i] + 1) / 2.0)
            rgb[py, px, 0] = 30.0 * depth
            rgb[py, px, 1] = 220.0 * depth
            rgb[py, px, 2] = 160.0 * depth

    # Draw rungs (base pairs) at regular intervals
    rung_u = np.linspace(0.05, 0.95, NUM_RUNGS)
    for i in range(NUM_RUNGS):
        ui = rung_u[i]
        idx = int(round(ui * (N_PER_STRAND - 1)))
        px_a = int(round(xa[idx]))
        px_b = int(round(xb[idx]))
        py_r = int(round(ya[idx]))

        if not (0 <= py_r < H):
            continue

        # depth: use the average z
        depth_r = max(0.2, ((za[idx] + zb[idx]) / 2.0 + 1) / 2.0)

        x_min = max(0, min(px_a, px_b))
        x_max = min(W - 1, max(px_a, px_b))

        if x_min <= x_max:
            # Color: yellow-ish / green for rungs
            c_r = 100.0 * depth_r
            c_g = 200.0 * depth_r
            c_b = 50.0 * depth_r
            rgb[py_r, x_min:x_max + 1, 0] = np.maximum(rgb[py_r, x_min:x_max + 1, 0], c_r)
            rgb[py_r, x_min:x_max + 1, 1] = np.maximum(rgb[py_r, x_min:x_max + 1, 1], c_g)
            rgb[py_r, x_min:x_max + 1, 2] = np.maximum(rgb[py_r, x_min:x_max + 1, 2], c_b)

    # Slight glow: blur by averaging with neighbors (vectorized, no per-pixel loop)
    # Use a simple 3x3 box blur via slicing
    glow = np.zeros_like(rgb)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
            glow += shifted
    glow /= 9.0
    rgb = 0.7 * rgb + 0.3 * glow

    # Clamp to 0-255
    rgb = np.clip(rgb, 0.0, 255.0)
    return rgb.astype(np.uint8)
