"""Neon city skyline with blinking windows.

A stylized neon cityscape: dark background, a row of buildings in various
neon colors, and their windows flicker on/off with pseudo-random patterns
deterministic per building and window. A slow horizontal "scan" highlight
sweeps across the scene. Loops seamlessly over DURATION.
"""
import math

import numpy as np

NAME = "neon_city_skyline"
DURATION = 30
FPS = 20

W = 64
H = 64
N_BUILDINGS = 10
PERIOD = 10.0  # all periodic elements have period PERIOD (divides DURATION)
SWEEP_PERIOD = PERIOD * 2.0  # sweep period, also divides DURATION


def init(w, h):
    # Precompute grid
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)

    # Building layout: x_start, width, height, color index
    # We'll create N_BUILDINGS buildings across the 64-wide screen
    building_width = 6  # each building 6 px wide (64 / 10 = 6.4)
    layout = []
    for i in range(N_BUILDINGS):
        bx = int(i * W / N_BUILDINGS)
        bw = max(4, int(W / N_BUILDINGS) - 1)
        # Vary heights
        hgt = int(15 + 30 * abs(math.sin(0.7 * i + 1.2)))
        hgt = max(12, min(hgt, 48))
        color_idx = i % 6
        layout.append((bx, bw, hgt, color_idx))

    # Precompute building masks and per-building window grids
    # For each building, define window positions
    # Windows: within building, every 2 px horizontally and 3 px vertically
    buildings = []
    for (bx, bw, hgt, color_idx) in layout:
        # Window grid within building
        cols = max(1, bw // 2)
        rows = max(1, hgt // 3)
        # Window x positions (centered within building)
        wx = bx + 1 + np.arange(cols) * 2
        wx = np.clip(wx, bx, bx + bw - 1)
        # Window y positions (top of building = H - hgt)
        top = H - hgt
        wy = top + 1 + np.arange(rows) * 3
        wy = np.clip(wy, top, H - 1)
        buildings.append({
            "bx": bx,
            "bw": bw,
            "hgt": hgt,
            "top": top,
            "color_idx": color_idx,
            "wx": wx,
            "wy": wy,
        })

    # Precompute neon colors (6 distinct saturated colors)
    neon_colors = np.array([
        [255, 40, 120],   # pink
        [0, 200, 255],    # cyan
        [255, 100, 0],    # orange
        [120, 255, 50],   # lime
        [180, 80, 255],   # purple
        [255, 255, 50],   # yellow
    ], dtype=np.float32)

    # Precompute a seed-based pseudo-random mask for each window
    # Each window has a phase and a "duty" for flickering
    rng = np.random.default_rng(42)
    for b in buildings:
        n_win = len(b["wx"]) * len(b["wy"])
        b["phase"] = rng.random(n_win).astype(np.float32) * 2 * math.pi
        b["flicker_rate"] = rng.uniform(0.3, 1.5, size=n_win).astype(np.float32)
        b["bright_base"] = rng.uniform(0.3, 0.7, size=n_win).astype(np.float32)

    # Precompute building mask (for silhouette)
    bmask = np.zeros((H, W), dtype=bool)
    for b in buildings:
        bmask[b["top"]:b["top"] + b["hgt"], b["bx"]:b["bx"] + b["bw"]] = True

    return {
        "y": y,
        "x": x,
        "buildings": buildings,
        "neon_colors": neon_colors,
        "bmask": bmask,
        "w": w,
        "h": h,
    }


def render(state, t):
    w = state["w"]
    h = state["h"]
    buildings = state["buildings"]
    neon_colors = state["neon_colors"]
    bmask = state["bmask"]

    # Create RGB image
    img = np.zeros((h, w, 3), dtype=np.float32)

    # Draw building silhouettes (dark base)
    img[bmask] = [20, 15, 30]

    # Sweep highlight: a vertical band of light moving across
    # Position based on time
    sweep_pos = (t / SWEEP_PERIOD) * (w + 20) - 10  # -10 to w+10
    # Gaussian falloff
    x_grid = state["x"]
    sweep_intensity = np.exp(-((x_grid - sweep_pos) ** 2) / (8.0 ** 2))
    # Add sweep to building areas
    for c in range(3):
        img[:, :, c] += sweep_intensity * [0.15, 0.1, 0.25][c] * 255 * bmask

    # Draw windows
    for b in buildings:
        bx, bw, top, hgt = b["bx"], b["bw"], b["top"], b["hgt"]
        wx, wy = b["wx"], b["wy"]
        color = neon_colors[b["color_idx"]]
        n_cols = len(wx)
        n_rows = len(wy)
        n_win = n_cols * n_rows

        # Reshape phase, rate, base into (rows, cols)
        phase = b["phase"].reshape(n_rows, n_cols)
        rate = b["flicker_rate"].reshape(n_rows, n_cols)
        base = b["bright_base"].reshape(n_rows, n_cols)

        # Time-varying flicker
        # Use sin for smooth on/off
        flick = 0.5 + 0.5 * np.sin(2 * math.pi * rate * t + phase)
        # Quantize to make it more "blinky" (step-like)
        flick = np.where(flick > 0.5, 1.0, 0.1)

        # Combine with base brightness
        bright = base * flick  # 0.03..0.7
        # Scale to 0..1 range, boost for visibility
        bright = np.clip(bright * 2.0, 0.0, 1.0)

        # Place windows
        for ri in range(n_rows):
            for ci in range(n_cols):
                yy = int(wy[ri])
                xx = int(wx[ci])
                if 0 <= yy < h and 0 <= xx < w:
                    b_val = bright[ri, ci]
                    if b_val > 0.05:
                        # Window is lit
                        img[yy, xx, 0] = max(img[yy, xx, 0], color[0] * b_val)
                        img[yy, xx, 1] = max(img[yy, xx, 1], color[1] * b_val)
                        img[yy, xx, 2] = max(img[yy, xx, 2], color[2] * b_val)

    # Add a subtle ground glow
    ground_row = h - 1
    img[ground_row, :, :] = np.maximum(img[ground_row, :, :], [30, 20, 50])

    # Clip to 0-255
    img = np.clip(img, 0, 255)
    return img.astype(np.uint8)
