"""Heartbeat line on a green monitor: dark green background, bright green trace.

A single ECG-like trace sweeps across the 64x64 matrix. The period (8 s)
divides DURATION (40 s) so the animation loops seamlessly.
"""
import math

import numpy as np

NAME = "heartbeat_green"
DURATION = 40
FPS = 20

PERIOD = 8.0


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # Precompute a normalized 1D ECG waveform over 0..1
    xs = np.linspace(0.0, 1.0, 256, endpoint=False, dtype=np.float32)
    # Build a synthetic ECG shape using sum of Gaussians
    ecg = np.zeros_like(xs)
    # P wave
    ecg += 0.15 * np.exp(-((xs - 0.10) ** 2) / (2 * 0.015 ** 2))
    # QRS complex: Q down, R up, S down
    ecg -= 0.10 * np.exp(-((xs - 0.20) ** 2) / (2 * 0.008 ** 2))
    ecg += 0.60 * np.exp(-((xs - 0.22) ** 2) / (2 * 0.006 ** 2))
    ecg -= 0.12 * np.exp(-((xs - 0.24) ** 2) / (2 * 0.008 ** 2))
    # T wave
    ecg += 0.20 * np.exp(-((xs - 0.35) ** 2) / (2 * 0.018 ** 2))
    # Flatten the rest
    ecg[xs > 0.55] *= 0
    ecg[xs < 0.03] *= 0
    return {"x": x, "y": y, "xs": xs, "ecg": ecg}


def render(state, t):
    x, y = state["x"], state["y"]
    xs, ecg = state["xs"], state["ecg"]

    # Map t to a phase in [0, 1) over one period
    phase = (t / PERIOD) % 1.0

    # Build a 1D trace for the current phase: for each column, find where
    # the trace is by shifting the ecg waveform
    # The trace sweeps left to right; we draw the ecg waveform centered
    # at the head position. For each column x, compute distance to head.
    head = phase * 64.0  # head position in columns

    # For each column, compute the ecg value at (x - head) wrapped
    col = np.arange(64, dtype=np.float32)
    # offset = (col - head) mod 64, normalized to 0..1
    offset = ((col - head) % 64.0) / 64.0
    # Use the ecg waveform: only show if offset is within [0, 0.4] roughly
    # Map offset back to xs index
    idx = np.searchsorted(xs, offset)
    idx = np.clip(idx, 0, len(xs) - 1)
    trace_vals = ecg[idx]

    # Only show trace in a band around the center row
    # The trace is a 1-pixel tall line at y = center + trace_vals * scale
    center = 31.5
    scale = 20.0
    trace_y = center + trace_vals * scale

    # Create the output: dark green background
    rgb = np.empty((64, 64, 3), dtype=np.float32)
    # Dark green background
    rgb[..., 0] = 5.0
    rgb[..., 1] = 12.0
    rgb[..., 2] = 5.0

    # For each column, draw a bright green pixel at trace_y
    for i in range(64):
        ty = int(np.clip(trace_y[i], 0, 63))
        rgb[ty, i, 0] = 30.0
        rgb[ty, i, 1] = 200.0
        rgb[ty, i, 2] = 30.0
        # Add a slight glow above and below
        if ty > 0:
            rgb[ty - 1, i, 1] = max(rgb[ty - 1, i, 1], 60.0)
        if ty < 63:
            rgb[ty + 1, i, 1] = max(rgb[ty + 1, i, 1], 60.0)

    # Head marker: a brighter, slightly wider line at the head position
    hx = int(head) % 64
    hy = int(np.clip(trace_y[hx], 0, 63))
    for dy in range(-2, 3):
        for dx in range(-1, 2):
            nx = (hx + dx) % 64
            ny = hy + dy
            if 0 <= ny < 64:
                rgb[ny, nx, 0] = 80.0
                rgb[ny, nx, 1] = 240.0
                rgb[ny, nx, 2] = 80.0

    return rgb.astype(np.uint8)
