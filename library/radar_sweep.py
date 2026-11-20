"""Radar sweep with blips."""
import math

import numpy as np

NAME = "radar_sweep"
DURATION = 30
FPS = 20

PERIOD = 5.0
N_BLIPS = 12


def init(w, h):
    cx, cy = (w - 1) / 2, (h - 1) / 2
    x, y = np.mgrid[0:w, 0:h].astype(np.float32)
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    a = np.arctan2(y - cy, x - cx)  # -pi..pi
    rng = np.random.default_rng(42)
    blip_r = rng.uniform(4, 28, N_BLIPS).astype(np.float32)
    blip_a = rng.uniform(0, 2 * math.pi, N_BLIPS).astype(np.float32)
    blip_decay = rng.uniform(2.0, 4.0, N_BLIPS).astype(np.float32)
    blip_x = (cx + blip_r * np.cos(blip_a)).astype(np.float32)
    blip_y = (cy + blip_r * np.sin(blip_a)).astype(np.float32)
    return {
        "x": x,
        "y": y,
        "r": r,
        "a": a,
        "cx": cx,
        "cy": cy,
        "blip_r": blip_r,
        "blip_a": blip_a,
        "blip_decay": blip_decay,
        "blip_x": blip_x,
        "blip_y": blip_y,
    }


def render(state, t):
    x = state["x"]
    y = state["y"]
    r = state["r"]
    a = state["a"]
    cx, cy = state["cx"], state["cy"]
    W, H = x.shape

    # sweep angle
    phase = (t % PERIOD) / PERIOD  # 0..1
    sweep_a = phase * 2 * math.pi  # 0..2pi

    # angular distance behind sweep: (sweep_a - a) mod 2pi, in [0, 2pi)
    delta = (sweep_a - a) % (2 * math.pi)  # 0..2pi, 0 means just at sweep

    # trail intensity: fades over a portion of the circle
    trail_width = math.pi * 0.6
    trail = np.where(
        (delta < trail_width) & (r < 30),
        np.exp(-delta * 4.0),
        0.0
    ).astype(np.float32)
    trail *= (r <= 30).astype(np.float32)

    # grid rings
    rings = np.zeros((W, H), dtype=np.float32)
    for rr in [8, 16, 24, 30]:
        rings += np.exp(-((r - rr) ** 2) / 2.0)
    # crosshair
    cross = (np.exp(-(x - cx) ** 2 / 1.5) + np.exp(-(y - cy) ** 2 / 1.5)).astype(np.float32)
    cross *= (r <= 30).astype(np.float32)

    # blips
    blip_visible = np.zeros((W, H), dtype=np.float32)
    blip_a = state["blip_a"]
    blip_decay = state["blip_decay"]
    blip_x = state["blip_x"]
    blip_y = state["blip_y"]
    for i in range(N_BLIPS):
        ba = blip_a[i]
        db = (sweep_a - ba) % (2 * math.pi)
        time_since = db * PERIOD / (2 * math.pi)
        if time_since < PERIOD * 0.5:
            fade = np.exp(-time_since * blip_decay[i] * 0.3)
            bx, by = blip_x[i], blip_y[i]
            blob = np.exp(-((x - bx) ** 2 + (y - by) ** 2) / 4.0)
            blob *= (r <= 30).astype(np.float32)
            blip_visible += blob * fade

    # combine
    base = np.zeros((W, H, 3), dtype=np.float32)

    # dark background
    base[..., 0] = 2
    base[..., 1] = 6
    base[..., 2] = 10

    # rings and cross: dim green
    grid_val = rings * 0.3 + cross * 0.5
    base[..., 0] += grid_val * 10
    base[..., 1] += grid_val * 40
    base[..., 2] += grid_val * 15

    # sweep trail: bright green
    base[..., 0] += trail * 30
    base[..., 1] += trail * 200
    base[..., 2] += trail * 50

    # blips: bright amber/yellow
    base[..., 0] += blip_visible * 220
    base[..., 1] += blip_visible * 180
    base[..., 2] += blip_visible * 30

    # center dot
    center_dot = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / 2.0)
    base[..., 0] += center_dot * 150
    base[..., 1] += center_dot * 200
    base[..., 2] += center_dot * 50

    return np.clip(base, 0, 255).astype(np.uint8)
