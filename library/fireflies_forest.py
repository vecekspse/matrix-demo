"""Fireflies in a dark forest: dark teal background, drifting glowing orbs.

Deterministic: seeds fixed. Loop period = DURATION (phases wrap via modulo).
No per-pixel loops.
"""
import math

import numpy as np

NAME = "fireflies_forest"
DURATION = 30
FPS = 20

N_FLIES = 28
W, H = 64, 64


def init(w, h):
    rng = np.random.default_rng(1234)
    n = N_FLIES
    cx = rng.uniform(0, w, size=n)
    cy = rng.uniform(0, h, size=n)
    ax = rng.uniform(3.0, 12.0, size=n)
    ay = rng.uniform(3.0, 12.0, size=n)
    ph_x = rng.uniform(0, 2 * math.pi, size=n)
    ph_y = rng.uniform(0, 2 * math.pi, size=n)
    ph_p = rng.uniform(0, 2 * math.pi, size=n)
    blink_freq = rng.uniform(0.4, 1.4, size=n)
    radius = rng.uniform(3.0, 5.5, size=n)
    base_glow = rng.uniform(0.55, 1.0, size=n)

    return {
        "cx": cx, "cy": cy,
        "ax": ax, "ay": ay,
        "ph_x": ph_x, "ph_y": ph_y, "ph_p": ph_p,
        "blink_freq": blink_freq,
        "radius": radius,
        "base_glow": base_glow,
    }


def render(state, t):
    n = N_FLIES
    cx = state["cx"]
    cy = state["cy"]
    ax = state["ax"]
    ay = state["ay"]
    ph_x = state["ph_x"]
    ph_y = state["ph_y"]
    ph_p = state["ph_p"]
    blink_freq = state["blink_freq"]
    radius = state["radius"]
    base_glow = state["base_glow"]

    # Seamless loop: all angular frequencies are integer multiples of 2π/DURATION
    omega = 2 * math.pi / DURATION
    px = (cx + ax * np.sin(omega * t + ph_x)) % W
    py = (cy + ay * np.cos(omega * t * 0.7 + ph_y)) % H

    # Blink: smooth pulse, period divides DURATION via integer freq
    # Use: sin(omega * blink_freq * t + ph_p) mapped to [0,1] with power for sharpness
    blink_phase = np.sin(omega * blink_freq * t + ph_p)
    blink = np.clip(0.5 + 0.5 * blink_phase, 0.0, 1.0) ** 3

    # Intensity per fly
    intensity = base_glow * (0.15 + 0.85 * blink)

    img = np.zeros((H, W, 3), dtype=np.float32)

    for i in range(n):
        fi = int(np.round(px[i])) % W
        fj = int(np.round(py[i])) % H
        r = radius[i]
        inten = intensity[i]

        # Create a circular Gaussian glow
        local_r = np.arange(-int(r), int(r) + 1, dtype=np.float32)
        lx, ly = np.meshgrid(local_r, local_r, indexing="ij")
        dist_sq = lx * lx + ly * ly
        sigma_sq = (r * 0.45) ** 2
        glow = np.exp(-dist_sq / (2 * sigma_sq)) * inten

        # Clip to valid image bounds
        x_start = fi - int(r)
        y_start = fj - int(r)
        x_end = x_start + glow.shape[1]
        y_end = y_start + glow.shape[0]

        x0 = max(0, x_start)
        y0 = max(0, y_start)
        x1 = min(W, x_end)
        y1 = min(H, y_end)

        gx0 = x0 - x_start
        gy0 = y0 - y_start
        gx1 = x1 - x_start
        gy1 = y1 - y_start

        region = glow[gy0:gy1, gx0:gx1]

        # Warm yellow-green: R high, G high, B low
        img[y0:y1, x0:x1, 0] += region * 180
        img[y0:y1, x0:x1, 1] += region * 220
        img[y0:y1, x0:x1, 2] += region * 40

        # Bright core
        core_r = max(1, int(r * 0.25))
        clx = np.arange(-core_r, core_r + 1, dtype=np.float32)
        clx, cly = np.meshgrid(clx, clx, indexing="ij")
        cdist_sq = clx * clx + cly * cly
        csigma_sq = (core_r * 0.5) ** 2
        cglow = np.exp(-cdist_sq / (2 * csigma_sq)) * inten

        cx_start = fi - core_r
        cy_start = fj - core_r
        cx_end = cx_start + cglow.shape[1]
        cy_end = cy_start + cglow.shape[0]

        cx0 = max(0, cx_start)
        cy0 = max(0, cy_start)
        cx1 = min(W, cx_end)
        cy1 = min(H, cy_end)

        cgx0 = cx0 - cx_start
        cgy0 = cy0 - cy_start
        cgx1 = cx1 - cx_start
        cgy1 = cy1 - cy_start

        core_region = cglow[cgy0:cgy1, cgx0:cgx1]
        img[cy0:cy1, cx0:cx1, 0] += core_region * 100
        img[cy0:cy1, cx0:cx1, 1] += core_region * 130
        img[cy0:cy1, cx0:cx1, 2] += core_region * 30

    # Dark forest background: very dark teal/green
    img[..., 0] = np.minimum(img[..., 0] + 5, 255)
    img[..., 1] = np.minimum(img[..., 1] + 12, 255)
    img[..., 2] = np.minimum(img[..., 2] + 8, 255)

    return np.clip(img, 0, 255).astype(np.uint8)
