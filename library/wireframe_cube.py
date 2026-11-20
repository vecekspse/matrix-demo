import math

import numpy as np

NAME = "wireframe_cube"
DURATION = 30
FPS = 20

# Precompute the 12 edges of a unit cube (each edge as two 3D vertices)
EDGES = np.array([
    [[-1, -1, -1], [1, -1, -1]],
    [[1, -1, -1], [1, 1, -1]],
    [[1, 1, -1], [-1, 1, -1]],
    [[-1, 1, -1], [-1, -1, -1]],
    [[-1, -1, 1], [1, -1, 1]],
    [[1, -1, 1], [1, 1, 1]],
    [[1, 1, 1], [-1, 1, 1]],
    [[-1, 1, 1], [-1, -1, 1]],
    [[-1, -1, -1], [-1, -1, 1]],
    [[1, -1, -1], [1, -1, 1]],
    [[1, 1, -1], [1, 1, 1]],
    [[-1, 1, -1], [-1, 1, 1]],
], dtype=np.float32)

N_EDGES = 12
# Each edge is a segment in 3D; we'll project and draw as line segments.

def init(w, h):
    # Precompute pixel coordinates for drawing line segments
    y_grid, x_grid = np.mgrid[0:h, 0:w].astype(np.float32)
    state = {
        "w": w,
        "h": h,
        "y": y_grid,
        "x": x_grid,
        "edges": EDGES,
    }
    return state

def _draw_segment(buf, x0, y0, x1, y1, color, thickness=2):
    """Draw a thick line segment on buf (H,W,3) uint8 array using vectorized approach."""
    h, w = buf.shape[:2]
    # Use midpoint / parametric sampling along the segment
    # Number of samples based on length
    dx = x1 - x0
    dy = y1 - y0
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.5:
        # Just a point
        cx, cy = int(round(x0)), int(round(y0))
        for ox in range(-thickness, thickness + 1):
            for oy in range(-thickness, thickness + 1):
                px, py = cx + ox, cy + oy
                if 0 <= px < w and 0 <= py < h:
                    buf[py, px] = color
        return

    n_samples = max(int(length * 2) + 1, 2)
    ts = np.linspace(0.0, 1.0, n_samples)
    xs = x0 + dx * ts
    ys = y0 + dy * ts
    xs = np.clip(np.round(xs).astype(int), 0, w - 1)
    ys = np.clip(np.round(ys).astype(int), 0, h - 1)

    # Set each sampled pixel to color
    for i in range(n_samples):
        buf[ys[i], xs[i]] = color

    # Add thickness by offsetting in 4 directions
    for ox in range(-thickness, thickness + 1):
        for oy in range(-thickness, thickness + 1):
            if ox == 0 and oy == 0:
                continue
            xs2 = np.clip(xs + ox, 0, w - 1)
            ys2 = np.clip(ys + oy, 0, h - 1)
            for i in range(n_samples):
                buf[ys2[i], xs2[i]] = color

def render(state, t):
    w, h = state["w"], state["h"]
    edges = state["edges"]

    # Rotation angles: seamless loop with DURATION
    # Use periods that divide DURATION (30s)
    # RotX period 10s -> 3 full rotations
    # RotY period 15s -> 2 full rotations
    # RotZ period 30s -> 1 full rotation
    theta_x = 2 * math.pi * t / 10.0
    theta_y = 2 * math.pi * t / 15.0
    theta_z = 2 * math.pi * t / 30.0

    cx, cy, cz = math.cos(theta_x), math.sin(theta_x), 0.0
    cy2, sy2, _ = math.cos(theta_y), math.sin(theta_y), 0.0
    cz2, sz2, _ = math.cos(theta_z), math.sin(theta_z), 0.0

    # Rotation matrices
    Rx = np.array([[1, 0, 0],
                   [0, cx, -sy2],  # placeholder
                   [0, 0, 1]], dtype=np.float32)
    # Let's build properly
    Rx = np.array([[1, 0, 0],
                   [0, math.cos(theta_x), -math.sin(theta_x)],
                   [0, math.sin(theta_x), math.cos(theta_x)]], dtype=np.float32)

    Ry = np.array([[math.cos(theta_y), 0, math.sin(theta_y)],
                   [0, 1, 0],
                   [-math.sin(theta_y), 0, math.cos(theta_y)]], dtype=np.float32)

    Rz = np.array([[math.cos(theta_z), -math.sin(theta_z), 0],
                   [math.sin(theta_z), math.cos(theta_z), 0],
                   [0, 0, 1]], dtype=np.float32)

    # Combined rotation
    R = Rz @ (Ry @ Rx)

    # Transform all vertices
    # EDGES shape (12, 2, 3)
    vertices_3d = edges.reshape(N_EDGES * 2, 3) @ R.T  # (24, 3)
    # Add perspective: project to 2D
    # Place camera at z = -4 looking toward origin
    z_cam = 4.0
    # Perspective projection
    z_vals = vertices_3d[:, 2] + z_cam  # shift so z is positive in front
    # Avoid division by zero / negative
    z_vals = np.where(z_vals < 0.1, 0.1, z_vals)
    # Scale to fit 64x64
    scale = 18.0
    px = vertices_3d[:, 0] * scale / z_vals * z_cam
    py = vertices_3d[:, 1] * scale / z_vals * z_cam
    # Center on screen
    px = px + w / 2.0
    py = -py + h / 2.0  # flip y

    # Clip to screen bounds (keep all, drawing will clip)
    px = px.astype(np.float32)
    py = py.astype(np.float32)

    # Start with black background
    buf = np.zeros((h, w, 3), dtype=np.uint8)

    # Color: use depth-based shading - closer edges brighter
    # Compute average depth per edge
    # Each edge i has vertices 2*i and 2*i+1
    edge_depths = (z_vals.reshape(N_EDGES, 2)).mean(axis=1)
    # Normalize depth: min depth = farthest (largest z), max depth = closest (smallest z)
    depth_min = edge_depths.min()
    depth_max = edge_depths.max()
    depth_range = depth_max - depth_min
    if depth_range < 1e-6:
        intensity = np.ones(N_EDGES, dtype=np.float32)
    else:
        # Closer (smaller z) -> brighter
        intensity = (depth_max - edge_depths) / depth_range
        intensity = np.clip(intensity, 0.2, 1.0)

    # Color: cyan/blue gradient based on intensity
    # Closest: bright cyan (0, 255, 255), farthest: dim blue (0, 50, 120)
    for i in range(N_EDGES):
        x0 = px[2 * i]
        y0 = py[2 * i]
        x1 = px[2 * i + 1]
        y1 = py[2 * i + 1]
        # Only draw if at least partially on screen
        if (x0 < -2 or x0 > w + 2 or y0 < -2 or y0 > h + 2 and
            x1 < -2 or x1 > w + 2 or y1 < -2 or y1 > h + 2):
            # Check if segment intersects screen
            pass

        c = intensity[i]
        color = np.array([
            int(0 * c),
            int(50 + 205 * c),
            int(120 + 135 * c),
        ], dtype=np.uint8)

        # Draw segment
        _draw_segment(buf, x0, y0, x1, y1, color, thickness=1)

    # Draw vertices as slightly brighter points for emphasis
    for i in range(24):
        vx = px[i]
        vy = py[i]
        if 0 <= int(vx) < w and 0 <= int(vy) < h:
            ix, iy = int(vx), int(vy)
            buf[iy, ix] = np.array([30, 220, 255], dtype=np.uint8)
            # 3x3 small glow
            for ox in range(-1, 2):
                for oy in range(-1, 2):
                    px2, py2 = ix + ox, iy + oy
                    if 0 <= px2 < w and 0 <= py2 < h:
                        buf[py2, px2] = np.maximum(buf[py2, px2], np.array([30, 220, 255], dtype=np.uint8))

    return buf
