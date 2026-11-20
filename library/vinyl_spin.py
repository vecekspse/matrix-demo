"""Spinning vinyl record with sweeping light reflections and grooves."""
import math
import numpy as np

NAME = "vinyl_spin"
DURATION = 30
FPS = 20

N_GROOVES = 9
LIGHT_PERIOD = 15.0
SPIN_PERIOD = 30.0
SPEED_LINES = 4


def init(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    x0 = x - cx
    y0 = y - cy
    r = np.sqrt(x0 * x0 + y0 * y0)
    theta = np.arctan2(y0, x0)
    return {"x0": x0, "y0": y0, "r": r, "theta": theta, "cx": cx, "cy": cy}


def render(state, t):
    x0, y0 = state["x0"], state["y0"]
    r, theta = state["r"], state["theta"]
    cx, cy = state["cx"], state["cy"]

    # Record geometry (radius in px)
    outer_r = 30.0
    label_r = 10.0
    hub_r = 3.0

    # Seamless rotation phase
    spin_phase = 2.0 * math.pi * t / SPIN_PERIOD

    # ---- Base: black record body with subtle grooves ----
    in_record = r < outer_r
    # Radial grooves: sin( r * freq - spin_phase * k ) -> creates rotating groove shimmer
    groove_wave = np.sin(r * 1.4 - spin_phase * 2.0)
    groove_bright = 0.05 + 0.05 * groove_wave  # subtle dark/light bands
    body = np.where(in_record, groove_bright, 0.0)

    # ---- Label (center colored disc) ----
    in_label = (r >= label_r) & (r < outer_r)
    in_hub = r < label_r
    # Label color: warm red/orange with a subtle radial gradient
    label_grad = np.clip(1.0 - r / label_r, 0.0, 1.0)
    label_r_c = 180.0
    label_g_c = 30.0
    label_b_c = 20.0

    body_rgb_r = body * 20.0
    body_rgb_g = body * 12.0
    body_rgb_b = body * 10.0

    # Apply label colors
    body_rgb_r = np.where(in_hub, label_r_c * (0.6 + 0.4 * label_grad), body_rgb_r)
    body_rgb_g = np.where(in_hub, label_g_c * (0.6 + 0.4 * label_grad), body_rgb_g)
    body_rgb_b = np.where(in_hub, label_b_c * (0.6 + 0.4 * label_grad), body_rgb_b)

    # Spindle (tiny bright dot in center)
    in_spindle = r < hub_r
    body_rgb_r = np.where(in_spindle, 200.0, body_rgb_r)
    body_rgb_g = np.where(in_spindle, 200.0, body_rgb_g)
    body_rgb_b = np.where(in_spindle, 210.0, body_rgb_b)

    # ---- Rotating "speed lines" / radial streaks on the record ----
    # Several thin angular bands that rotate with the record
    n_lines = SPEED_LINES
    streak_total = 0.0
    for k in range(n_lines):
        offset = (2.0 * math.pi * k / n_lines)
        # Angular position of the streak relative to the rotating frame
        ang_diff = theta + spin_phase - offset
        # Wrap to [-pi, pi]
        ang_diff = np.arctan(np.tan(ang_diff))
        # Width of streak (radians)
        width = 0.12
        # Gaussian-like falloff: cos( ang_diff / width * pi/2 )^2 for |ang_diff|<width
        mask = np.abs(ang_diff) < width
        intensity = np.zeros_like(r)
        if np.any(mask):
            normalized = np.abs(ang_diff) / width  # 0..1
            falloff = np.cos(normalized * math.pi / 2.0) ** 2
            intensity = np.where(mask, falloff * 0.35, 0.0)
        # Only on the record, not on the label
        intensity = np.where(in_record & ~in_hub, intensity, 0.0)
        streak_total += intensity

    # Add streaks as warm white
    streak_total = np.clip(streak_total, 0.0, 0.5)
    body_rgb_r = body_rgb_r + streak_total * 180.0
    body_rgb_g = body_rgb_g + streak_total * 160.0
    body_rgb_b = body_rgb_b + streak_total * 150.0

    # ---- Sweeping light reflection (specular highlight) ----
    # A bright angular band that sweeps across the record, rotating at a different rate
    # Use a period that divides DURATION for seamless loop
    light_angle = 2.0 * math.pi * t / LIGHT_PERIOD
    # The reflection is a narrow angular band
    ang_diff_light = theta - light_angle
    ang_diff_light = np.arctan(np.tan(ang_diff_light))
    light_width = 0.25
    light_mask = np.abs(ang_diff_light) < light_width
    light_int = np.zeros_like(r)
    if np.any(light_mask):
        norm_l = np.abs(ang_diff_light) / light_width
        falloff_l = np.cos(norm_l * math.pi / 2.0) ** 2
        light_int = np.where(light_mask, falloff_l * 1.0, 0.0)

    # Reflection only on the vinyl surface (not label, not outside)
    on_vinyl = in_record & ~in_hub
    light_int = np.where(on_vinyl, light_int, 0.0)

    # The reflection intensity also depends slightly on radius (more on outer)
    radius_factor = np.clip((r - label_r) / (outer_r - label_r), 0.0, 1.0)
    light_int = light_int * (0.4 + 0.6 * radius_factor)

    # Add bright white/cyan specular highlight
    body_rgb_r = body_rgb_r + light_int * 220.0
    body_rgb_g = body_rgb_g + light_int * 230.0
    body_rgb_b = body_rgb_b + light_int * 255.0

    # Slight blue tint on the outer edge for depth
    edge_band = np.clip((r - outer_r + 2.0) / 4.0, 0.0, 1.0)
    edge_band = np.where(in_record, edge_band, 0.0)
    body_rgb_b = body_rgb_b + edge_band * 30.0

    # ---- Clamp and output ----
    rgb = np.stack([body_rgb_r, body_rgb_g, body_rgb_b], axis=-1)
    rgb = np.clip(rgb, 0.0, 255.0)
    return rgb.astype(np.uint8)
