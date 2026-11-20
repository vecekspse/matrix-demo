"""Bleskova boure nad morem: tma, tyrkyske vlny, biele blešky a obcasny blesk."""
import math

import numpy as np

NAME = "lightning_sea"
DURATION = 30
FPS = 20

PERIOD = 15.0
N_BOLTS = 5


def init(w, h):
    rng = np.random.default_rng(12345)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    wave1 = np.sin(x * 0.18 + y * 0.12)
    wave2 = np.sin(x * 0.09 - y * 0.20)
    wave3 = np.sin((x + y) * 0.10)

    bolt_specs = []
    for _ in range(N_BOLTS):
        # start near top, end near sea horizon (y ~ 20..30)
        x0 = rng.uniform(0.1, 0.9) * (w - 1)
        x1 = x0 + rng.uniform(-6, 6)
        y0 = rng.uniform(0.0, 4.0)
        y1 = rng.uniform(18.0, 28.0)
        n_pts = 6
        ts = np.linspace(0, 1, n_pts)
        segs = []
        px = [x0]
        py = [y0]
        for i in range(1, n_pts):
            nx = x0 + (x1 - x0) * ts[i] + rng.uniform(-4, 4) * (1 - ts[i])
            ny = y0 + (y1 - y0) * ts[i] + rng.uniform(-2, 2)
            segs.append((px[-1], py[-1], nx, ny))
            px.append(nx)
            py.append(ny)
        bolt_specs.append((np.array(px, dtype=np.float32), np.array(py, dtype=np.float32), segs))

    return {
        "x": x,
        "y": y,
        "r": r,
        "w1": wave1,
        "w2": wave2,
        "w3": wave3,
        "bolts": bolt_specs,
        "w": w,
        "h": h,
    }


def _bolt_brightness(x, y, segs, xres, yres, center_y):
    """Vectorized distance-to-segment brightness for one bolt."""
    # accumulate intensity from each segment
    inten = np.zeros((yres, xres), dtype=np.float32)
    for x0, y0, x1, y1 in segs:
        dx = x1 - x0
        dy = y1 - y0
        L2 = dx * dx + dy * dy + 1e-6
        # projection of (px - x0) onto segment
        t = np.clip(((x - x0) * dx + (y - y0) * dy) / L2, 0.0, 1.0)
        pxs = x0 + t * dx
        pys = y0 + t * dy
        d = np.sqrt((x - pxs) ** 2 + (y - pys) ** 2)
        inten += np.exp(-d * d * 0.6)
    return inten


def render(state, t):
    x, y, r = state["x"], state["y"], state["r"]
    w1, w2, w3 = state["w1"], state["w2"], state["w3"]
    h = state["h"]
    w = state["w"]
    bolts = state["bolts"]

    a = 2 * math.pi * t / PERIOD

    # sea: base dark blue-green, moving waves
    sea_mask = y >= 22.0
    wave = (np.sin(x * 0.14 + a * 1.0)
            + np.sin(y * 0.10 - a * 0.8)
            + w1 * 0.3 + w2 * 0.2)
    wave = (wave + 2.5) / 5.0
    wave = np.clip(wave, 0.0, 1.0)

    sky_v = np.where(y < 22.0, 1.0, 0.0)
    sea_v = np.where(y >= 22.0, 1.0, 0.0)

    # sky gradient: darker at top
    sky_grad = 1.0 - (y / max(h, 1)) * 0.5
    sky_grad = np.clip(sky_grad, 0.3, 1.0)

    # base colors
    rgb = np.empty((h, w, 3), dtype=np.float32)
    # sky: deep blue
    rgb[..., 0] = np.where(sea_v > 0.5, 15 + 40 * wave, 20 * sky_grad)
    rgb[..., 1] = np.where(sea_v > 0.5, 50 + 80 * wave, 40 * sky_grad)
    rgb[..., 2] = np.where(sea_v > 0.5, 80 + 100 * wave, 90 * sky_grad)

    # lightning flashes: each bolt fires at a different sub-time in the period
    # fire times: evenly spaced
    for i, (bpx, bpy, segs) in enumerate(bolts):
        fire_t = (i / N_BOLTS) * PERIOD
        # delta time from fire, wrapped
        dt = (t - fire_t) % PERIOD
        # short flash: bright for ~0.15s, decay over ~0.4s
        flash = 0.0
        if dt < 0.05:
            flash = 1.0
        elif dt < 0.4:
            flash = 1.0 - (dt - 0.05) / 0.35
        flash = max(0.0, flash)
        if flash < 0.01:
            continue
        inten = _bolt_brightness(x, y, segs, w, h, 22)
        glow = flash * inten
        # white-hot core
        rgb[..., 0] += np.clip(glow * 255, 0, 255)
        rgb[..., 1] += np.clip(glow * 255, 0, 255)
        rgb[..., 2] += np.clip(glow * 240, 0, 255)
        # sky illumination
        sky_glow = flash * np.exp(-r * 0.04) * 0.6
        rgb[..., 0] += sky_glow * 180 * sky_v
        rgb[..., 1] += sky_glow * 200 * sky_v
        rgb[..., 2] += sky_glow * 220 * sky_v
        # sea reflection
        sea_glow = flash * np.exp(-((y - 25) ** 2) * 0.08) * np.exp(-((x - (w - 1) / 2) ** 2) * 0.005) * 0.5
        rgb[..., 0] += sea_glow * 160 * sea_v
        rgb[..., 1] += sea_glow * 180 * sea_v
        rgb[..., 2] += sea_glow * 200 * sea_v

    # sparkle on sea highlights
    sparkle = np.where((wave > 0.75) & (sea_v > 0.5), 1.0, 0.0)
    rgb[..., 0] += sparkle * 60
    rgb[..., 1] += sparkle * 80
    rgb[..., 2] += sparkle * 90

    np.clip(rgb, 0, 255, out=rgb)
    return rgb.astype(np.uint8)
