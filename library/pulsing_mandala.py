"""Pulsing mandala: radiating petal patterns with breathing intensity and color cycling."""
import math

import numpy as np

NAME = "pulsing_mandala"
DURATION = 30
FPS = 20

PERIOD = 10.0
PETALS = 12
RING_COUNT = 5


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    dx = x - cx
    dy = y - cy
    r = np.sqrt(dx ** 2 + dy ** 2)
    theta = np.arctan2(dy, dx)
    return {
        "r": r,
        "theta": theta,
    }


def render(state, t):
    r = state["r"]
    theta = state["theta"]

    a = 2 * math.pi * t / PERIOD
    breath = 0.6 + 0.4 * math.sin(a)
    spin = a * 0.5

    # Build petal pattern: sum of ring patterns with angular modulation
    v = np.zeros_like(r, dtype=np.float32)
    for i in range(RING_COUNT):
        ring_r = 5.0 + i * 8.0
        phase = a * (1.0 + 0.3 * i) + i * 0.7
        radial = np.exp(-((r - ring_r) ** 2) / (2.0 * (2.5 + 0.5 * i) ** 2))
        angular = np.cos(theta * PETALS + spin * (i + 1) + phase)
        v += radial * (angular + 1.0) * 2.0  # scale up to ensure visible values

    # Normalize and apply breathing
    v_max = RING_COUNT * 4.0
    v = np.clip(v / v_max, 0.0, 1.0)
    v = np.clip(v * breath * 2.0, 0.0, 1.0)

    # Add central glow
    center_glow = np.exp(-(r ** 2) / (2.0 * 10.0 ** 2)) * 0.6 * breath
    v = np.clip(v + center_glow, 0.0, 1.0)

    # Use a simple color scheme based on radius for high contrast
    # Inner: warm (orange/red), Outer: cool (blue/cyan)
    hue_factor = np.clip(r / 30.0, 0.0, 1.0)
    hue_factor = hue_factor + 0.1 * math.sin(a)
    hue_factor = np.clip(hue_factor, 0.0, 1.0)

    # Map hue_factor to RGB using a gradient: red -> yellow -> cyan -> blue
    # Simplified: use direct channel mapping with v as intensity
    # R: strong at center, fades out
    # G: strong in middle
    # B: strong at edge
    
    r_chan = np.exp(-((r - 10.0) ** 2) / (2.0 * 15.0 ** 2)) * v
    g_chan = np.exp(-((r - 20.0) ** 2) / (2.0 * 12.0 ** 2)) * v
    b_chan = np.exp(-((r - 30.0) ** 2) / (2.0 * 10.0 ** 2)) * v

    # Add some color cycling by shifting the radial centers with time
    shift = 5.0 * math.sin(a * 0.5)
    r_chan2 = np.exp(-((r - (10.0 + shift)) ** 2) / (2.0 * 15.0 ** 2)) * v
    g_chan2 = np.exp(-((r - (20.0 + shift * 0.5)) ** 2) / (2.0 * 12.0 ** 2)) * v
    b_chan2 = np.exp(-((r - (30.0 - shift)) ** 2) / (2.0 * 10.0 ** 2)) * v

    # Blend
    r_out = np.clip(r_chan * 0.5 + r_chan2 * 0.5, 0.0, 1.0) * 255.0
    g_out = np.clip(g_chan * 0.5 + g_chan2 * 0.5, 0.0, 1.0) * 255.0
    b_out = np.clip(b_chan * 0.5 + b_chan2 * 0.5, 0.0, 1.0) * 255.0

    rgb = np.stack([r_out, g_out, b_out], axis=-1)
    return rgb.astype(np.uint8)
