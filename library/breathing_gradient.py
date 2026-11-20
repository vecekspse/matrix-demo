"""Breathing color gradient."""
import math

import numpy as np

NAME = "breathing_gradient"
DURATION = 30
FPS = 20
PERIOD = 10.0


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return {"x": x, "y": y}


def render(state, t):
    x, y = state["x"], state["y"]
    a = 2 * math.pi * t / PERIOD

    # Breathing scale
    scale = 1.0 + 0.3 * math.sin(a)

    # Normalize coordinates
    cx = 31.5
    cy = 31.5
    nx = (x - cx) / 31.5
    ny = (y - cy) / 31.5

    # Radial coordinate
    r = np.sqrt(nx ** 2 + ny ** 2)

    # Angle for hue variation
    theta = np.arctan2(ny, nx)

    # Gradient: radial with color shift
    # Use sin and cos to create a breathing color field
    color1 = np.sin(a + r * 2.0 + theta)
    color2 = np.sin(a * 0.7 + r * 1.5 - theta)
    color3 = np.sin(a * 1.3 + r * 2.5 + 0.5)

    # Combine into RGB
    # Map -1..1 to 0..1
    red = np.clip((color1 + 1) / 2 * scale, 0.0, 1.0)
    green = np.clip((color2 + 1) / 2 * scale, 0.0, 1.0)
    blue = np.clip((color3 + 1) / 2 * scale, 0.0, 1.0)

    # Boost saturation by scaling
    red = np.clip(red * 255, 0, 255)
    green = np.clip(green * 255, 0, 255)
    blue = np.clip(blue * 255, 0, 255)

    rgb = np.stack((red, green, blue), axis=-1)
    return rgb.astype(np.uint8)
