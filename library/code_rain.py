"""Falling green code rain: dark background, vertical green streams with bright heads.

Uses precomputed column parameters with a fixed seed for determinism. Each column
has a speed and phase; heads are bright, tails fade. Loops seamlessly because
the effective head position uses modulo and the fade is based on the distance.
"""
import math

import numpy as np

NAME = "code_rain"
DURATION = 20
FPS = 20

SEED = 42
N_COLS = 64
HEAD_HEIGHT = 4  # pixels of bright head
TAIL_HEIGHT = 28  # pixels of fading tail
SPEEDS_MIN = 12.0
SPEEDS_MAX = 30.0


def init(w, h):
    rng = np.random.default_rng(SEED)
    speeds = rng.uniform(SPEEDS_MIN, SPEEDS_MAX, size=N_COLS).astype(np.float32)
    phases = rng.uniform(0.0, 64.0, size=N_COLS).astype(np.float32)
    brightness = rng.uniform(0.4, 1.0, size=N_COLS).astype(np.float32)

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)

    return {
        "w": w,
        "h": h,
        "y": y,
        "speeds": speeds,
        "phases": phases,
        "brightness": brightness,
        "head_height": HEAD_HEIGHT,
        "tail_height": TAIL_HEIGHT,
    }


def render(state, t):
    h = state["h"]
    y = state["y"]  # shape (h, w)
    speeds = state["speeds"]  # shape (w,)
    phases = state["phases"]  # shape (w,)
    brightness = state["brightness"]  # shape (w,)
    head_h = state["head_height"]
    tail_h = state["tail_height"]

    # For each column, the head position at time t:
    # head_y = (phases + speeds * t) % h
    head_y = (phases + speeds * t) % h  # shape (w,)
    head_y_exp = head_y[None, :]  # shape (1, w)

    # Distance below head (wraps around)
    dist = (y - head_y_exp) % h  # shape (h, w), values 0..h-1

    # Head and tail masks
    head_mask = dist < head_h
    tail_mask = (dist >= head_h) & (dist < head_h + tail_h)

    # Tail fade: linear from 1 to 0 over tail_h pixels
    tail_fade = np.where(tail_mask, 1.0 - (dist - head_h) / tail_h, 0.0)

    # Combined intensity
    intensity = np.where(head_mask, 1.0, tail_fade)  # shape (h, w)

    # Apply per-column brightness
    intensity = intensity * brightness[None, :]

    # Color: green with slight blue tint
    g = 255.0 * intensity
    b = 255.0 * intensity * 0.25
    r = np.zeros_like(g)

    # Stack into (h, w, 3)
    rgb = np.stack([r, g, b], axis=-1)

    # Clip to 0..255
    rgb = np.clip(rgb, 0.0, 255.0)

    return rgb.astype(np.uint8)
