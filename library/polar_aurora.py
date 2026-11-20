"""Polar aurora: waving green/cyan/cyan ribbons over a dark horizon."""
import math

import numpy as np

NAME = "polar_aurora"
DURATION = 40
FPS = 20

PERIOD = 20.0
HORIZON_Y = 42


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # sky rows only (above horizon)
    sky_mask = (y < HORIZON_Y).astype(np.float32)
    # vertical distance above horizon for wave shaping
    sky_v = np.where(y < HORIZON_Y, (HORIZON_Y - y) / (HORIZON_Y + 1), 0.0)
    sky_v = np.clip(sky_v, 0.0, 1.0)
    # precompute x phase offsets
    x_phase = x * 0.12
    return {
        "x": x,
        "y": y,
        "sky_mask": sky_mask,
        "sky_v": sky_v,
        "x_phase": x_phase,
        "w": w,
        "h": h,
    }


def render(state, t):
    x, y = state["x"], state["y"]
    sky_mask = state["sky_mask"]
    sky_v = state["sky_v"]
    x_phase = state["x_phase"]

    a = 2 * math.pi * t / PERIOD

    # Multiple wave layers
    w1 = np.sin(x_phase + a * 1.0 + np.sin(x * 0.05) * 0.5)
    w2 = np.sin(x_phase * 0.7 - a * 1.5 + 1.2)
    w3 = np.sin(x_phase * 1.3 + a * 0.8 + 2.5)

    # Vertical wave displacement
    wave_y = (w1 * 0.6 + w2 * 0.8 + w3 * 0.5) * 12.0

    # Compute vertical position of the aurora band center
    band_center = 28.0 + wave_y
    # Band width
    band_width = 10.0 + 3.0 * w2

    # Distance from band center
    dist = np.abs(y - band_center)

    # Intensity: Gaussian-like falloff
    intensity = np.exp(-0.5 * (dist / band_width) ** 2) * sky_mask
    # Fade with altitude
    intensity *= (1.0 - 0.3 * sky_v)

    # Horizontal drift modulation
    drift = 0.7 + 0.3 * np.sin(x * 0.08 + a * 0.5)
    intensity *= drift

    # Clip and scale
    intensity = np.clip(intensity, 0.0, 1.0)

    # Color: green base, cyan highlights, slight purple at top
    # Base hue shifts with wave
    hue_shift = 0.0 + 0.1 * w3  # subtle hue variation

    # Green channel
    green = 220.0 * intensity
    # Cyan: blue + green
    blue = 120.0 * intensity * (0.8 + 0.2 * w1)
    # Red: small amount for warmth at edges
    red = 20.0 * intensity ** 2

    # Add bright core
    core = intensity ** 3
    green += 40.0 * core
    blue += 30.0 * core

    # Dark horizon / ground
    ground_mask = (y >= HORIZON_Y).astype(np.float32)
    # Ground: very dark blue-gray
    ground_r = 5.0
    ground_g = 8.0
    ground_b = 14.0

    # Stars in the upper sky
    star_seed = np.random.default_rng(42)
    # Precomputed in init? We'll do a simple deterministic star field
    # Using a fixed pattern based on x,y
    star_val = np.sin(x * 12.345 + y * 7.654) * np.cos(x * 5.678 - y * 3.456)
    stars = np.where((star_val > 0.92) & (y < 20), 80.0, 0.0) * sky_mask
    stars += np.where((np.sin(x * 9.876 + y * 4.321) > 0.93) & (y < 15), 60.0, 0.0) * sky_mask

    # Compose
    r = np.where(ground_mask > 0, ground_r, red) + stars * 0.5
    g = np.where(ground_mask > 0, ground_g, green) + stars * 0.5
    b = np.where(ground_mask > 0, ground_b, blue) + stars * 0.8

    # Horizon line glow
    horizon_glow = np.exp(-0.5 * (np.abs(y - (HORIZON_Y - 1.0)) / 2.0) ** 2) * sky_mask
    g += 30.0 * horizon_glow
    b += 15.0 * horizon_glow

    rgb = np.stack([r, g, b], axis=-1)
    rgb = np.clip(rgb, 0, 255)
    return rgb.astype(np.uint8)
