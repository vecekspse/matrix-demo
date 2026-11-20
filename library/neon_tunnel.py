"""Neon tunnel: dark background, concentric neon rings scrolling toward the viewer.

Each ring is a bright square frame whose thickness and glow scale with the
distance from the viewer. Period is 6 s, DURATION (30 s) is a whole number of
periods so the animation loops seamlessly.
"""
import math

import numpy as np

NAME = "neon_tunnel"
DURATION = 30
FPS = 20

PERIOD = 6.0


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = (w - 1) / 2
    cy = (h - 1) / 2
    # Chebyshev (square) distance from the centre
    d = np.maximum(np.abs(x - cx), np.abs(y - cy))
    return {"x": x, "y": y, "cx": cx, "cy": cy, "d": d, "w": w, "h": h}


def render(state, t):
    d = state["d"]
    cx = state["cx"]
    cy = state["cy"]
    w = state["w"]
    h = state["h"]

    a = 2 * math.pi * (t / PERIOD)
    ring_count = 14
    max_d = max(w, h)

    # Accumulate intensity and colour across all rings
    total = np.zeros((h, w, 3), dtype=np.float32)

    for i in range(ring_count):
        phase = a + 2 * math.pi * i / ring_count
        # depth parameter in [0, 1): 0 = far, 1 = near viewer
        u = (phase / (2 * math.pi)) % 1.0
        # radius in pixels, shrinks as u -> 1
        radius = max_d * (1.0 - u)

        # ring band width
        thick = 1.0 + 2.0 * u
        # brightness falls off with distance (perspective)
        bright = 0.15 + 0.85 * (u ** 2)

        # band mask: |d - radius| < thick/2
        diff = np.abs(d - radius)
        band = np.clip(1.0 - diff / (thick * 0.5 + 0.5), 0.0, 1.0)

        # hue cycles over time
        hue = (0.55 + 0.45 * math.sin(a + i * 0.5)) % 1.0
        # simple hue -> RGB
        h6 = hue * 6.0
        r_c = max(0.0, min(1.0, 1.0 - abs(h6 - 0) - 1.0))
        g_c = max(0.0, min(1.0, 1.0 - abs(h6 - 2) + 1.0))
        b_c = max(0.0, min(1.0, 1.0 - abs(h6 - 4) + 1.0))

        intensity = band * bright
        total[..., 0] += intensity * r_c * 255
        total[..., 1] += intensity * g_c * 255
        total[..., 2] += intensity * b_c * 255

    # Add a glowing centre (vanishing point)
    centre_glow = np.exp(-4.0 * (d / max_d) ** 2)
    total[..., 0] += centre_glow * 80
    total[..., 1] += centre_glow * 200
    total[..., 2] += centre_glow * 255

    # Clip to 0..255
    total = np.clip(total, 0, 255)
    return total.astype(np.uint8)
