import math

import numpy as np

NAME = "sunrise_hills"
DURATION = 30
FPS = 20


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt((x - (w - 1) / 2) ** 2 + (y - (h - 1) / 2) ** 2)
    state = {"x": x, "y": y, "r": r}
    return state


def render(state, t):
    # Normalize time to 0..1 over DURATION
    p = t / DURATION  # 0..1

    x = state["x"]
    y = state["y"]
    r = state["r"]

    # --- Sun position: rises from bottom-center to top-center
    cx = 32.0
    cy = 50.0 - 35.0 * p  # starts at y=50 (bottom), ends at y=15 (upper)
    # Sun radius
    sun_r = 8.0

    # Distance to sun center
    dsun = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    # --- Sky gradient: dark blue at top to warm orange near horizon
    # Horizon is at y ~ 40 (hills base)
    horizon_y = 40.0
    # Sky color: interpolate from dark blue (top) to deep purple (bottom)
    # As sun rises, sky brightens
    sky_progress = p  # 0=pre-dawn, 1=full sunrise

    # Base sky colors (dark blue -> warm)
    sky_top_r = np.full((64, 64), 5, dtype=np.float32)
    sky_top_g = np.full((64, 64), 5, dtype=np.float32)
    sky_top_b = np.full((64, 64), 30, dtype=np.float32)

    # Gradient: y=0 (top) to y=horizon_y
    y_norm = y / horizon_y  # 0 at top, 1 at horizon
    y_norm_clipped = np.clip(y_norm, 0, 1)

    # Top color (dark blue-purple)
    top_r = 5.0 + 20 * sky_progress
    top_g = 5.0 + 5 * sky_progress
    top_b = 30.0 + 10 * sky_progress

    # Horizon color (deep orange-warm as sun rises)
    hor_r = 20.0 + 180 * sky_progress
    hor_g = 5.0 + 60 * sky_progress
    hor_b = 40.0 + 20 * sky_progress

    # Interpolate vertically
    sky_r = top_r + (hor_r - top_r) * y_norm_clipped
    sky_g = top_g + (hor_g - top_g) * y_norm_clipped
    sky_b = top_b + (hor_b - top_b) * y_norm_clipped

    # --- Sun glow: radial gradient
    sun_glow = np.clip(1.0 - dsun / (sun_r * 4.0), 0, 1)
    sun_glow = sun_glow ** 1.5
    # Sun core (bright white-yellow)
    sun_core = np.clip(1.0 - dsun / sun_r, 0, 1)
    sun_core = sun_core ** 1.2

    # Sun color: warm yellow-white
    sun_r_c = 255
    sun_g_c = 200 + 40 * p
    sun_b_c = 80

    # Add sun contribution
    sky_r += sun_glow * 150 * sky_progress
    sky_g += sun_glow * 100 * sky_progress
    sky_b += sun_glow * 50 * sky_progress

    sky_r += sun_core * 255 * sky_progress
    sky_g += sun_core * 220 * sky_progress
    sky_b += sun_core * 150 * sky_progress

    # --- Hills: 3 layers of rolling hills
    # Hill base at y=40, extending down
    # Use sine waves for rolling hills

    # Hill layer 1 (farthest, darkest)
    hill1_y = 40.0 + 8 * np.sin(x * 0.15 + 0.5)
    # Hill layer 2 (middle)
    hill2_y = 48.0 + 10 * np.sin(x * 0.12 - 0.3)
    # Hill layer 3 (nearest, darkest)
    hill3_y = 55.0 + 12 * np.sin(x * 0.1 + 0.8)

    # Create masks: pixel is hill if y > hill_y
    is_hill1 = y >= hill1_y
    is_hill2 = y >= hill2_y
    is_hill3 = y >= hill3_y

    # Hill colors (dark silhouettes, slightly varying)
    # Far hills: dark blue-black
    hill1_r = 10 + 10 * sky_progress
    hill1_g = 8 + 8 * sky_progress
    hill1_b = 20 + 10 * sky_progress

    # Middle hills: slightly lighter
    hill2_r = 5 + 5 * sky_progress
    hill2_g = 4 + 4 * sky_progress
    hill2_b = 15 + 5 * sky_progress

    # Near hills: darkest
    hill3_r = 3 + 3 * sky_progress
    hill3_g = 2 + 2 * sky_progress
    hill3_b = 10 + 3 * sky_progress

    # Apply hills (draw from far to near, so nearer hills overwrite)
    sky_r = np.where(is_hill1, hill1_r, sky_r)
    sky_g = np.where(is_hill1, hill1_g, sky_g)
    sky_b = np.where(is_hill1, hill1_b, sky_b)

    sky_r = np.where(is_hill2, hill2_r, sky_r)
    sky_g = np.where(is_hill2, hill2_g, sky_g)
    sky_b = np.where(is_hill2, hill2_b, sky_b)

    sky_r = np.where(is_hill3, hill3_r, sky_r)
    sky_g = np.where(is_hill3, hill3_g, sky_g)
    sky_b = np.where(is_hill3, hill3_b, sky_b)

    # --- Stars (visible before sunrise, fade out as sun rises)
    # Precompute star positions (deterministic, fixed seed in init? No, use fixed)
    # We'll use a simple hash-based approach for stars
    # Stars are small bright dots in upper sky
    # Use a fixed pattern based on coordinates
    # Create a few bright pixels as stars
    star_seed = np.zeros((64, 64), dtype=np.float32)
    # Use a pseudo-random but deterministic pattern
    # Simple approach: stars where (x*7 + y*13) % 47 == 0 and y < 25
    star_mask = ((x * 7 + y * 13) % 47 == 0) & (y < 25)
    # Brighten stars
    star_brightness = 180 * (1.0 - p * 2.0)  # fade out by p=0.5
    star_brightness = np.clip(star_brightness, 0, 255)

    sky_r = np.where(star_mask, np.maximum(sky_r, star_brightness), sky_r)
    sky_g = np.where(star_mask, np.maximum(sky_g, star_brightness), sky_g)
    sky_b = np.where(star_mask, np.maximum(sky_b, star_brightness + 30), sky_b)

    # --- Clamp and convert
    rgb = np.stack([sky_r, sky_g, sky_b], axis=-1)
    rgb = np.clip(rgb, 0, 255)
    return rgb.astype(np.uint8)
