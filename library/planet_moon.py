"""Rotating planet with an orbiting moon.

A simple stylised planet spins (procedural stripes) while a smaller moon
circulates around it. The moon's orbit period and the planet's stripe
frequency are both 10 s so the whole scene loops seamlessly within the
DURATION.
"""
import math

import numpy as np

NAME = "planet_moon"
DURATION = 30
FPS = 20

ORBIT_PERIOD = 10.0
SPIN_PERIOD = 10.0


def init(w, h):
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    x, y = np.mgrid[0:w, 0:h].astype(np.float32)

    # Planet geometry
    px = x - cx
    py = y - cy
    planet_r = 18.0
    planet_dist_sq = px * px + py * py
    planet_mask = planet_dist_sq <= planet_r * planet_r

    # Precompute a static stripe pattern in "planet space".
    # We use a latitude-like coordinate (py) combined with a longitudinal
    # offset that will be animated by shifting the pattern horizontally.
    # To make the planet look spherical, we scale the longitude by the
    # chord width at that latitude (classic equirectangular-ish shading).
    sin_lat = np.clip(py / planet_r, -1.0, 1.0)
    cos_lat = np.sqrt(np.maximum(1.0 - sin_lat * sin_lat, 0.0))
    # Longitude in [0, 1) across the visible hemisphere; we will shift it.
    lon = np.arctan2(px, np.abs(py) + 1e-3) / math.pi  # roughly -1..1
    # Normalize to 0..1 for tiling
    lon_norm = (lon + 1.0) / 2.0

    # Store what we need
    state = {
        "cx": cx,
        "cy": cy,
        "planet_r": planet_r,
        "planet_mask": planet_mask,
        "cos_lat": cos_lat,
        "sin_lat": sin_lat,
        "lon_norm": lon_norm,
        "px": px,
        "py": py,
        "w": w,
        "h": h,
    }
    return state


def render(state, t):
    w, h = state["w"], state["h"]
    cx, cy = state["cx"], state["cy"]
    planet_r = state["planet_r"]
    planet_mask = state["planet_mask"]
    cos_lat = state["cos_lat"]
    sin_lat = state["sin_lat"]
    lon_norm = state["lon_norm"]
    px, py = state["px"], state["py"]

    # Spin phase: one full rotation per SPIN_PERIOD
    spin_phase = t / SPIN_PERIOD  # cycles

    # Build the planet's surface: stripes that move with the spin.
    # The longitude on the surface that is currently at the centre is
    # lon_center = spin_phase (mod 1). We shift lon_norm by that amount.
    lon_shifted = (lon_norm - spin_phase) % 1.0

    # Stripe pattern: a few broad bands.
    # Use a 1-D periodic function of lon_shifted * cos_lat to simulate
    # spherical wrapping.
    stripe_arg = lon_shifted * 4.0 * cos_lat + 0.5 * sin_lat
    stripe_val = (np.sin(stripe_arg * 2 * math.pi) + 1.0) / 2.0  # 0..1

    # Planet body colour: deep blue-green with lighter bands.
    base_r = 20.0
    base_g = 60.0
    base_b = 120.0
    band_r = 80.0
    band_g = 180.0
    band_b = 140.0

    pr = base_r + (band_r - base_r) * stripe_val
    pg = base_g + (band_g - base_g) * stripe_val
    pb = base_b + (band_b - base_b) * stripe_val

    # Add simple 3D shading: brighter on the upper-left.
    shade = 0.6 + 0.4 * np.clip((-px * 0.5 - py * 0.5) / planet_r + 0.5, 0.0, 1.0)
    pr *= shade
    pg *= shade
    pb *= shade

    # Create output array
    frame = np.zeros((h, w, 3), dtype=np.float32)

    # Dark space background
    frame[..., 0] = 5
    frame[..., 1] = 5
    frame[..., 2] = 15

    # Draw planet
    frame[planet_mask, 0] = pr[planet_mask]
    frame[planet_mask, 1] = pg[planet_mask]
    frame[planet_mask, 2] = pb[planet_mask]

    # Planet edge: a subtle rim light
    edge = planet_dist_sq_state = px * px + py * py
    edge_mask = (edge > (planet_r - 1.5) ** 2) & planet_mask
    frame[edge_mask, 0] += 30
    frame[edge_mask, 1] += 30
    frame[edge_mask, 2] += 30

    # Moon
    orbit_radius = 30.0
    orbit_angle = 2 * math.pi * (t / ORBIT_PERIOD)
    moon_x = cx + orbit_radius * math.cos(orbit_angle)
    moon_y = cy + orbit_radius * math.sin(orbit_angle) * 0.5  # elliptical for depth
    # Determine if moon is "behind" the planet (farther away): y offset sign
    behind = math.sin(orbit_angle) < 0  # top half is behind
    z_factor = 0.7 if behind else 1.0

    moon_r = 5.0 * z_factor
    # Moon position in pixel grid
    mx = int(round(moon_x))
    my = int(round(moon_y))

    # Draw moon as a filled circle
    for dy in range(int(-moon_r) - 1, int(moon_r) + 2):
        for dx in range(int(-moon_r) - 1, int(moon_r) + 2):
            xx = mx + dx
            yy = my + dy
            if 0 <= xx < w and 0 <= yy < h:
                dist_sq = dx * dx + dy * dy
                if dist_sq <= moon_r * moon_r:
                    # Moon colour: pale grey with slight shading
                    m_shade = 0.7 + 0.3 * np.clip((-dx * 0.3 - dy * 0.3) / moon_r + 0.5, 0.0, 1.0)
                    mr = 180 * m_shade
                    mg = 180 * m_shade
                    mb = 190 * m_shade
                    # If moon is behind planet, skip drawing over planet
                    if not (behind and (px[yy, xx] ** 2 + py[yy, xx] ** 2) <= planet_r ** 2):
                        frame[yy, xx, 0] = mr
                        frame[yy, xx, 1] = mg
                        frame[yy, xx, 2] = mb

    return np.clip(frame, 0, 255).astype(np.uint8)
