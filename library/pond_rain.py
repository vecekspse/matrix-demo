"""Dark pond: falling rain drops create expanding ripples on a deep-blue water surface."""
import math

import numpy as np

NAME = "pond_rain"
DURATION = 30
FPS = 20

N_DROPS = 22
PERIOD = 30.0  # equals DURATION for a seamless loop
MAX_RIPPLE_R = 30.0  # max ripple radius in pixels


def init(w, h):
    rng = np.random.default_rng(42)
    x, y = np.mgrid[0:w, 0:h].astype(np.float32)

    # Precompute grid distance from center (for subtle background depth)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    bg_r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    # Drop parameters: each drop gets a spawn time offset (mod PERIOD), x, y
    spawn_times = np.sort(rng.uniform(0, PERIOD, size=N_DROPS)).astype(np.float32)
    drop_x = rng.uniform(4, w - 4, size=N_DROPS).astype(np.float32)
    drop_y = rng.uniform(4, h - 4, size=N_DROPS).astype(np.float32)
    # Vary ripple intensity slightly
    amplitudes = rng.uniform(0.7, 1.3, size=N_DROPS).astype(np.float32)

    return {
        "x": x,
        "y": y,
        "bg_r": bg_r,
        "spawn_times": spawn_times,
        "drop_x": drop_x,
        "drop_y": drop_y,
        "amplitudes": amplitudes,
        "w": w,
        "h": h,
    }


def render(state, t):
    x, y = state["x"], state["y"]
    bg_r = state["bg_r"]
    spawn_times = state["spawn_times"]
    drop_x = state["drop_x"]
    drop_y = state["drop_y"]
    amplitudes = state["amplitudes"]
    w, h = state["w"], state["h"]

    # Wrap t to [0, PERIOD) for seamless loop
    t_wrapped = t % PERIOD

    # Ripple strength accumulation: for each drop, compute how much it contributes
    # at every pixel. Ripple expands from radius 0 to MAX_RIPPLE_R over a fixed
    # duration (say 4 seconds), with amplitude decaying as it expands.
    RIPPLE_LIFE = 4.0
    ripple_intensity = np.zeros((h, w), dtype=np.float32)
    ripple_phase = np.zeros((h, w), dtype=np.float32)  # not strictly needed, but useful

    for i in range(len(drop_x)):
        dt = (t_wrapped - spawn_times[i]) % PERIOD
        # Only active if within ripple life
        if dt < RIPPLE_LIFE:
            # Ripple radius: linear growth
            radius = (dt / RIPPLE_LIFE) * MAX_RIPPLE_R
            # Distance from drop
            dist = np.sqrt((x - drop_x[i]) ** 2 + (y - drop_y[i]) ** 2)
            # Ring thickness increases slightly as ripple expands
            thickness = 1.5 + radius * 0.15
            # How close is the pixel to the ripple ring
            diff = np.abs(dist - radius)
            # Gaussian-like falloff
            ring = np.exp(-(diff ** 2) / (2 * thickness ** 2))
            # Amplitude decays with time and radius
            decay = (1.0 - dt / RIPPLE_LIFE) * amplitudes[i]
            ripple_intensity += ring * decay
            ripple_phase += dt / RIPPLE_LIFE  # track phase for potential oscillation

    # Normalize ripple intensity
    max_ripple = np.max(ripple_intensity) if ripple_intensity.size > 0 else 1.0
    if max_ripple > 0:
        ripple_intensity = ripple_intensity / max_ripple

    # Base water color: deep dark blue with subtle radial gradient
    base_depth = np.clip(bg_r / 40.0, 0.0, 1.0)
    base_r = np.full((h, w), 5.0, dtype=np.float32)
    base_g = np.full((h, w), 10.0, dtype=np.float32)
    base_b = np.full((h, w), 25.0, dtype=np.float32)
    base_b = base_b + (1.0 - base_depth) * 15.0  # slightly brighter in center

    # Ripple effect: brighter blue-cyan highlights
    # The ripple creates a bright ring on top of the dark water
    ripple_r = base_r + ripple_intensity * 40.0
    ripple_g = base_g + ripple_intensity * 120.0
    ripple_b = base_b + ripple_intensity * 180.0

    # Add a subtle secondary wave: slower, broader ripples
    t_slow = t_wrapped / 15.0  # 15s period (divides 30)
    a = 2 * math.pi * t_slow
    wave = np.sin((x + y) * 0.08 + a) * 0.5 + np.sin(bg_r * 0.15 - 2 * a) * 0.5
    wave = np.clip(wave, -1, 1)
    ripple_r += wave * 3.0
    ripple_g += wave * 8.0
    ripple_b += wave * 12.0

    # Clip and convert
    rgb = np.stack([ripple_r, ripple_g, ripple_b], axis=-1)
    rgb = np.clip(rgb, 0.0, 255.0)
    return rgb.astype(np.uint8)
