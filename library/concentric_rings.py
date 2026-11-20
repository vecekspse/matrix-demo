"""Concentric color rings expanding from the center.

Rings move outward in a loop.  Each ring has a hue that shifts over time.
Seamless loop because all frequencies are integer multiples of 2*Pi / DURATION.
"""
import math

import numpy as np

NAME = "concentric_rings"
DURATION = 30
FPS = 20


def init(w, h):
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    return {"x": x, "y": y, "r": r, "max_r": math.sqrt(cx ** 2 + cy ** 2)}


def _hsv_to_rgb(h):
    """Vectorized HSV to RGB, h in [0,1) -> RGB in [0,1]."""
    h = np.mod(h, 1.0)
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    i = i.astype(np.int32) % 6
    v = 1.0
    s = 1.0
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    c0 = np.where(i == 0, v, np.where(i == 1, q, np.where(i == 2, p, np.where(i == 3, p, np.where(i == 4, t, v)))))
    c1 = np.where(i == 0, t, np.where(i == 1, v, np.where(i == 2, q, np.where(i == 3, p, np.where(i == 4, p, t)))))
    c2 = np.where(i == 0, p, np.where(i == 1, p, np.where(i == 2, v, np.where(i == 3, t, np.where(i == 4, q, p)))))
    return np.stack([c0, c1, c2], axis=-1)


def render(state, t):
    r = state["r"]
    max_r = state["max_r"]
    a = 2 * math.pi * t / DURATION

    # Ring pattern: rings expand outward.
    phase1 = r * 0.5 - a * 2.0
    phase2 = r * 0.35 + a * 3.0

    v1 = np.sin(phase1)
    v2 = np.sin(phase2)

    v = v1 * 0.7 + v2 * 0.3
    v_norm = (v + 1.0) * 0.5

    ring = np.where(v_norm > 0.7, 1.0, 0.0)
    glow = v_norm ** 8.0

    hue = (r / max_r + a / (2 * math.pi)) % 1.0

    rgb_base = _hsv_to_rgb(hue)  # shape (64, 64, 3)

    # Multiply each channel by scalar mask
    glow_expanded = glow[..., np.newaxis]
    ring_expanded = ring[..., np.newaxis]

    rgb = np.zeros((r.shape[0], r.shape[1], 3), dtype=np.float32)
    rgb += rgb_base * glow_expanded * 0.25
    rgb += rgb_base * ring_expanded * 1.0

    rgb = np.clip(rgb, 0.0, 1.0)
    rgb *= 1.3
    rgb = np.clip(rgb, 0.0, 1.0)

    return (rgb * 255).astype(np.uint8)
