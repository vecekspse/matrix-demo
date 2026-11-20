import math

import numpy as np

NAME = "bouncing_glow_trails"
DURATION = 30
FPS = 20

N_BALLS = 6
TRAIL_LEN = 12
W0 = 64


def init(w, h):
    rng = np.random.default_rng(123)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    px = (x - cx) / 32.0
    py = (y - cy) / 32.0
    rr = np.sqrt(px * px + py * py)

    # Precompute per-ball parameters
    base_pos = rng.standard_normal((N_BALLS, 2)).astype(np.float32) * 14.0
    freqs = (1.0 + rng.integers(0, 3, size=N_BALLS)).astype(np.float32)
    phases = (rng.standard_normal(N_BALLS) * 2 * math.pi).astype(np.float32)
    amplitudes = (5.0 + rng.standard_normal(N_BALLS) * 2.0).astype(np.float32)

    # Precompute base colors (6 distinct hues)
    base_hues = np.linspace(0.0, 1.0, N_BALLS, endpoint=False)
    # Simple hue to RGB conversion
    r_base = np.zeros(N_BALLS, dtype=np.float32)
    g_base = np.zeros(N_BALLS, dtype=np.float32)
    b_base = np.zeros(N_BALLS, dtype=np.float32)
    for i in range(N_BALLS):
        h = base_hues[i] * 6.0
        if h < 1:
            r_base[i], g_base[i], b_base[i] = 1.0, h, 0.0
        elif h < 2:
            r_base[i], g_base[i], b_base[i] = 2.0 - h, 1.0, 0.0
        elif h < 3:
            r_base[i], g_base[i], b_base[i] = 0.0, 1.0, h - 2.0
        elif h < 4:
            r_base[i], g_base[i], b_base[i] = 0.0, 4.0 - h, 1.0
        elif h < 5:
            r_base[i], g_base[i], b_base[i] = h - 4.0, 0.0, 1.0
        else:
            r_base[i], g_base[i], b_base[i] = 1.0, 0.0, 6.0 - h

    # Precompute trail offsets and fades
    trail_offsets = np.arange(TRAIL_LEN, dtype=np.float32) * (1.0 / FPS)
    trail_fades = (1.0 - (np.arange(TRAIL_LEN) + 1) / (TRAIL_LEN + 1)) ** 1.5
    trail_radii = np.array([4.0 - 0.2 * k for k in range(TRAIL_LEN)], dtype=np.float32)

    return {
        "x": x, "y": y, "cx": cx, "cy": cy, "rr": rr,
        "base_pos": base_pos,
        "freqs": freqs,
        "phases": phases,
        "amplitudes": amplitudes,
        "r_base": r_base,
        "g_base": g_base,
        "b_base": b_base,
        "trail_offsets": trail_offsets,
        "trail_fades": trail_fades,
        "trail_radii": trail_radii,
    }


def render(state, t):
    x, y = state["x"], state["y"]
    cx, cy = state["cx"], state["cy"]
    base_pos = state["base_pos"]
    freqs = state["freqs"]
    phases = state["phases"]
    amplitudes = state["amplitudes"]
    r_base = state["r_base"]
    g_base = state["g_base"]
    b_base = state["b_base"]
    trail_offsets = state["trail_offsets"]
    trail_fades = state["trail_fades"]
    trail_radii = state["trail_radii"]

    n = base_pos.shape[0]
    canvas = np.zeros((y.shape[0], y.shape[1], 3), dtype=np.float32)

    # Precompute ball positions for current time and trail times
    # For each ball i: position at time t - offset
    # x_i(t') = cx + base_pos[i,0] + amplitudes[i] * sin(2*pi*t'*freqs[i]/PERIOD + phases[i])
    # y_i(t') = cy + base_pos[i,1] + amplitudes[i] * cos(2*pi*t'*freqs[i]/PERIOD + phases[i] + 0.7)

    PERIOD = 5.0
    # For each ball and each trail step, compute position
    # Vectorize over balls for each trail step, or over trail steps for each ball
    # Let's do: for each ball, compute all trail positions at once

    for i in range(n):
        # Ball parameters
        bx_base = cx + base_pos[i, 0]
        by_base = cy + base_pos[i, 1]
        amp = amplitudes[i]
        freq = freqs[i]
        phase = phases[i]

        # Current time and trail times
        times = t - trail_offsets  # shape (TRAIL_LEN,)
        a = 2 * math.pi * times * freq / PERIOD + phase  # shape (TRAIL_LEN,)

        # Positions
        tx = bx_base + amp * np.sin(a)  # shape (TRAIL_LEN,)
        ty = by_base + amp * np.cos(a + 0.7)  # shape (TRAIL_LEN,)

        # For each trail position, compute glow contribution
        # dist2 = (x - tx[k])^2 + (y - ty[k])^2 for all pixels
        # We need to sum over k of exp(-dist2 / (2*radius[k]^2)) * fade[k] * color

        # Vectorize over trail steps: broadcast tx, ty to (TRAIL_LEN, H, W)
        tx_b = tx[:, None, None]  # (TRAIL_LEN, 1, 1)
        ty_b = ty[:, None, None]  # (TRAIL_LEN, 1, 1)
        x_b = x[None, :, :]  # (1, H, W)
        y_b = y[None, :, :]  # (1, H, W)

        dx = x_b - tx_b  # (TRAIL_LEN, H, W)
        dy = y_b - ty_b
        dist2 = dx * dx + dy * dy

        # radii shape (TRAIL_LEN,), fades shape (TRAIL_LEN,)
        radii_b = trail_radii[:, None, None]
        fades_b = trail_fades[:, None, None]

        # Gaussian falloff
        gauss = np.exp(-dist2 / (2.0 * radii_b * radii_b))  # (TRAIL_LEN, H, W)

        # Sum over trail steps
        intensity = np.sum(gauss * fades_b, axis=0)  # (H, W)

        # Color
        canvas[..., 0] += r_base[i] * intensity * 1.5
        canvas[..., 1] += g_base[i] * intensity * 1.5
        canvas[..., 2] += b_base[i] * intensity * 1.5

    # Add bright core for each ball
    for i in range(n):
        bx = cx + base_pos[i, 0]
        by = cy + base_pos[i, 1]
        a = 2 * math.pi * t * freqs[i] / PERIOD + phases[i]
        bx += amplitudes[i] * math.sin(a)
        by += amplitudes[i] * math.cos(a + 0.7)

        dist2 = (x - bx) ** 2 + (y - by) ** 2
        core = np.exp(-dist2 / (2.0 * 2.0 ** 2))
        glow = np.exp(-dist2 / (2.0 * 5.0 ** 2))

        canvas[..., 0] += r_base[i] * (core * 1.5 + glow * 0.5)
        canvas[..., 1] += g_base[i] * (core * 1.5 + glow * 0.5)
        canvas[..., 2] += b_base[i] * (core * 1.5 + glow * 0.5)

    canvas = np.clip(canvas, 0.0, 255.0)
    return canvas.astype(np.uint8)
