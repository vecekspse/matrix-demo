"""Plazma v barvach ocean: tmave modre pozadi, tyrkysove vlny, bile spicky.

Rucne psana ukazka kontraktu. Cykl ma periodu 15 s (vsechny frekvence jsou
celociselne nasobky), takze se plynule opakuje.
"""
import math

import numpy as np

NAME = "plasma_ocean"
DURATION = 45
FPS = 20

PERIOD = 15.0


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt((x - (w - 1) / 2) ** 2 + (y - (h - 1) / 2) ** 2)
    return {"x": x, "y": y, "r": r}


def render(state, t):
    a = 2 * math.pi * t / PERIOD
    x, y, r = state["x"], state["y"], state["r"]
    v = (np.sin(x * 0.16 + a)
         + np.sin(y * 0.13 - 2 * a)
         + np.sin((x + y) * 0.09 + a)
         + np.sin(r * 0.22 - 3 * a))              # -4..4
    v = np.clip((v + 4) / 8 * 1.6 - 0.3, 0.0, 1.0)  # 0..1, vyssi kontrast

    rgb = np.empty((v.shape[0], v.shape[1], 3), dtype=np.float32)
    rgb[..., 0] = 200 * v ** 6                    # svetle spicky
    rgb[..., 1] = 255 * v ** 2.2                  # tyrkys
    rgb[..., 2] = 255 * v ** 1.4                  # modra
    return rgb.astype(np.uint8)
