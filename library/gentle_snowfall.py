"""Sněžení nad tmavě modrou nocí."""
import math

import numpy as np

NAME = "gentle_snowfall"
DURATION = 30
FPS = 20
PERIOD = 30.0


def init(w, h):
    rng = np.random.default_rng(42)
    n = 150
    x0 = rng.uniform(0, w, size=n)
    y0 = rng.uniform(0, h, size=n)
    # Quantize vy so that vy * PERIOD is a multiple of h (64)
    k = rng.integers(3, 9, size=n).astype(np.float32)
    vy = k * h / PERIOD
    # Quantize drift frequency so it is periodic in PERIOD
    m = rng.integers(1, 5, size=n).astype(np.float32)
    drift_freq = m * 2 * math.pi / PERIOD
    drift_amp = rng.uniform(2.0, 8.0, size=n)
    phase = rng.uniform(0, 2 * math.pi, size=n)
    size = rng.uniform(1.5, 4.0, size=n)
    opacity = rng.uniform(0.5, 1.0, size=n)
    # Precompute integer grid positions and small patches
    y_grid, x_grid = np.mgrid[0:h, 0:w].astype(np.float32)

    state = {
        "x0": x0,
        "y0": y0,
        "vy": vy,
        "drift_freq": drift_freq,
        "drift_amp": drift_amp,
        "phase": phase,
        "size": size,
        "opacity": opacity,
        "y_grid": y_grid,
        "x_grid": x_grid,
        "w": w,
        "h": h,
    }
    return state


def render(state, t):
    w = state["w"]
    h = state["h"]
    y_grid = state["y_grid"]
    x_grid = state["x_grid"]
    x0 = state["x0"]
    y0 = state["y0"]
    vy = state["vy"]
    drift_freq = state["drift_freq"]
    drift_amp = state["drift_amp"]
    phase = state["phase"]
    size = state["size"]
    opacity = state["opacity"]
    n = x0.size

    # Compute positions
    y_pos = (y0 + vy * t) % h
    x_pos = (x0 + drift_amp * np.sin(drift_freq * t + phase)) % w

    # Start with dark blue background
    frame = np.zeros((h, w, 3), dtype=np.float32)
    frame[..., 0] = 5
    frame[..., 1] = 8
    frame[..., 2] = 18

    # Draw snowflakes vectorized using a threshold approach
    # For each pixel, compute minimum distance to any snowflake
    # Use broadcasting: (h*w, n) is too big, so do it in chunks or use a smarter approach
    # Instead, iterate over snowflakes but use precomputed small patches
    # Since n=150 and each patch is small (radius ~4-8), let's use a sparse approach
    
    # Alternative: for each snowflake, compute a small local patch
    # Precompute the max radius
    max_radius = (size * 2.0).max()
    patch_size = int(math.ceil(max_radius)) * 2 + 1
    
    for i in range(n):
        cx = x_pos[i]
        cy = y_pos[i]
        r = size[i] * 2.0
        op = opacity[i]
        
        # Local region
        x_min = max(0, int(cx - patch_size / 2))
        x_max = min(w, int(cx + patch_size / 2) + 1)
        y_min = max(0, int(cy - patch_size / 2))
        y_max = min(h, int(cy + patch_size / 2) + 1)
        
        if x_max <= x_min or y_max <= y_min:
            continue
        
        dx = x_grid[y_min:y_max, x_min:x_max] - cx
        dy = y_grid[y_min:y_max, x_min:x_max] - cy
        dist = np.sqrt(dx * dx + dy * dy)
        
        alpha = np.clip(1.0 - dist / r, 0.0, 1.0) ** 2.0
        alpha *= op
        
        # Skip if all zero
        if alpha.max() < 0.01:
            continue
        
        frame[y_min:y_max, x_min:x_max, 0] += 240 * alpha
        frame[y_min:y_max, x_min:x_max, 1] += 245 * alpha
        frame[y_min:y_max, x_min:x_max, 2] += 255 * alpha

    frame = np.clip(frame, 0, 255)
    return frame.astype(np.uint8)
