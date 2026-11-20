"""Fireworks bursting and fading on a 64x64 matrix.

Original design: dark background with multiple colored fireworks that burst
from random launch points, expand outward, and fade. Seamless loop with
period 8s (divides DURATION=32).
"""
import math

import numpy as np

NAME = "fireworks"
DURATION = 32
FPS = 20

PERIOD = 8.0
N_FIRE = 12
SPARKS = 18


def init(w, h):
    rng = np.random.default_rng(12345)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return {
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "launches": _make_launches(rng, w, h),
    }


def _make_launches(rng, w, h):
    launches = []
    for i in range(N_FIRE):
        cx = rng.integers(6, w - 6)
        cy = rng.integers(6, h - 6)
        hue = rng.random()
        phase = rng.random()
        speed = 0.7 + rng.random() * 0.6
        launches.append({
            "cx": float(cx),
            "cy": float(cy),
            "hue": hue,
            "phase": phase,
            "speed": speed,
            "sparks": _make_sparks(rng),
        })
    return launches


def _make_sparks(rng):
    angles = rng.uniform(0, 2 * math.pi, size=SPARKS)
    speeds = rng.uniform(0.6, 1.4, size=SPARKS)
    return {"angles": angles, "speeds": speeds}


def render(state, t):
    x, y = state["x"], state["y"]
    w, h = state["w"], state["h"]
    frame = np.zeros((h, w, 3), dtype=np.float32)

    for fire in state["launches"]:
        local_t = (t + fire["phase"] * PERIOD) % PERIOD
        progress = local_t / PERIOD

        # burst expands then fades
        if progress > 0.85:
            fade = max(0.0, 1.0 - (progress - 0.85) / 0.15)
        else:
            fade = min(1.0, progress / 0.1)

        if fade <= 0.001:
            continue

        radius = fire["speed"] * 24.0 * progress
        cx, cy = fire["cx"], fire["cy"]
        hue = fire["hue"]

        # main glow
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        glow = np.clip(1.0 - dist / (radius + 4.0), 0.0, 1.0) ** 2
        r_c, g_c, b_c = _hsv_to_rgb(hue)
        frame[..., 0] += glow * r_c * 180.0 * fade
        frame[..., 1] += glow * g_c * 180.0 * fade
        frame[..., 2] += glow * b_c * 180.0 * fade

        # sparks
        for angle, spd in zip(fire["sparks"]["angles"], fire["sparks"]["speeds"]):
            sx = cx + math.cos(angle) * radius * spd
            sy = cy + math.sin(angle) * radius * spd
            si = int(round(sx))
            sj = int(round(sy))
            if 0 <= si < w and 0 <= sj < h:
                # 3x3 block
                y0, y1 = max(0, sj - 1), min(h, sj + 2)
                x0, x1 = max(0, si - 1), min(w, si + 2)
                frame[y0:y1, x0:x1, 0] += r_c * 220.0 * fade
                frame[y0:y1, x0:x1, 1] += g_c * 220.0 * fade
                frame[y0:y1, x0:x1, 2] += b_c * 220.0 * fade

    return np.clip(frame, 0.0, 255.0).astype(np.uint8)


def _hsv_to_rgb(hue):
    """Return (r, g, b) floats in 0..1 for a hue in 0..1, saturated, bright."""
    h = (hue % 1.0) * 6.0
    i = int(h) % 6
    f = h - int(h)
    q = 1.0
    p = 0.15
    if i == 0:
        r, g, b = q, p + (q - p) * f, p
    elif i == 1:
        r, g, b = q - (q - p) * f, q, p
    elif i == 2:
        r, g, b = p, q, p + (q - p) * f
    elif i == 3:
        r, g, b = p, q - (q - p) * f, q
    elif i == 4:
        r, g, b = p + (q - p) * f, p, q
    else:
        r, g, b = q, p, q - (q - p) * f
    return r, g, b
