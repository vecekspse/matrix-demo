"""Akvarium s rybkami a bublinkami.

Tmave modre pozadi, 4 ryby plavouci v ruznych smerech,
bublinky stoupaji nahoru. Cyklus se plynule opakuje.
"""
import math

import numpy as np

NAME = "aquarium_fish"
DURATION = 60
FPS = 20

W, H = 64, 64
N_FISH = 4
N_BUBBLES = 14
SEED = 42


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    rng = np.random.default_rng(SEED)

    fish = []
    for i in range(N_FISH):
        speed = 18.0 + rng.random() * 14.0
        freq_x = (speed * DURATION) / (w - 1)
        freq_x = max(1, int(round(freq_x)))
        freq_y = max(1, int(round(rng.integers(2, 5))))
        phase_x = rng.uniform(0, 2 * math.pi)
        phase_y = rng.uniform(0, 2 * math.pi)
        fish.append({
            "fx": freq_x,
            "fy": freq_y,
            "px": phase_x,
            "py": phase_y,
            "dir": 1 if i % 2 == 0 else -1,
            "size": 5 + i,
            "r": int(rng.integers(180, 256)),
            "g": int(rng.integers(60, 200)),
            "b": int(rng.integers(40, 160)),
            "tail": 1.0 + rng.random() * 0.5,
        })

    bubbles = []
    for _ in range(N_BUBBLES):
        bx = float(rng.integers(0, w))
        speed = 8.0 + rng.random() * 12.0
        freq = (speed * DURATION) / (h - 1)
        freq = max(1, int(round(freq)))
        bubbles.append({
            "x": bx,
            "freq": freq,
            "phase": rng.uniform(0, 1),
            "wob": rng.uniform(0, 2 * math.pi),
            "wob_freq": max(1, int(round(rng.integers(2, 6)))),
            "wob_amp": rng.uniform(1.0, 3.0),
        })

    return {
        "x": x,
        "y": y,
        "cx": cx,
        "cy": cy,
        "fish": fish,
        "bubbles": bubbles,
    }


def _draw_fish(buf, state, f, t):
    xg, yg, cx, cy = state["x"], state["y"], state["cx"], state["cy"]
    phase = f["dir"] * (2 * math.pi * f["fx"] * t / DURATION + f["px"])
    fy = f["dir"] * (2 * math.pi * f["fy"] * t / DURATION + f["py"])
    fx = cx + (cx - 4) * math.cos(phase)
    fy_pos = cy + (cy - 10) * math.sin(fy) * 0.5

    tail_phase = 2 * math.pi * t / 0.4
    tail_dx = math.sin(tail_phase) * 2.0
    head_x = fx + f["dir"] * 2.0
    tail_x = fx - f["dir"] * 2.0 + tail_dx

    mask = np.zeros_like(xg, dtype=bool)
    dx = (xg - head_x) * f["dir"]
    mask |= (dx >= 0) & (dx <= 6) & (np.abs(yg - fy_pos) <= 2)
    dx_t = (xg - tail_x) * f["dir"]
    mask |= (dx_t < 0) & (dx_t > -4) & (np.abs(yg - fy_pos) <= 1)
    mask |= (dx > 0) & (dx <= 2) & (np.abs(yg - fy_pos) <= 1)

    r, g, b = f["r"], f["g"], f["b"]
    buf[mask, 0] = r
    buf[mask, 1] = g
    buf[mask, 2] = b
    eye_mask = (dx >= 1) & (dx <= 2) & (np.abs(yg - fy_pos + 0.5) <= 0.5)
    buf[eye_mask, 0] = 255
    buf[eye_mask, 1] = 255
    buf[eye_mask, 2] = 255


def _draw_bubble(buf, state, b, t):
    xg, yg = state["x"], state["y"]
    phase = 2 * math.pi * b["freq"] * t / DURATION + b["phase"]
    by = H - 1 - (H - 4) * (phase % (2 * math.pi)) / (2 * math.pi)
    wob = math.sin(2 * math.pi * b["wob_freq"] * t / DURATION + b["wob"]) * b["wob_amp"]
    bx = b["x"] + wob

    dist2 = (xg - bx) ** 2 + (yg - by) ** 2
    ring = (dist2 <= 4.0) & (dist2 >= 1.0)
    inner = dist2 < 1.0
    buf[ring, 0] = 180
    buf[ring, 1] = 230
    buf[ring, 2] = 255
    buf[inner, 0] = 120
    buf[inner, 1] = 200
    buf[inner, 2] = 255


def render(state, t):
    xg, yg = state["x"], state["y"]
    buf = np.zeros((H, W, 3), dtype=np.uint8)

    for fi in state["fish"]:
        _draw_fish(buf, state, fi, t)
    for bi in state["bubbles"]:
        _draw_bubble(buf, state, bi, t)

    return buf
