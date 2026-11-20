"""Prompt pro AI: kontrakt, pravidla, jeden kratky funkcni priklad.

Prompt je anglicky (spolehlivejsi i pro mensi lokalni modely). Napady
a chybove hlasky validatoru mohou byt cesky.
"""
import random
import re
from pathlib import Path

from runner import contract as C

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = (ROOT / "library" / "plasma_ocean.py").read_text(encoding="utf-8")

SYSTEM = f"""You write small Python animation modules for a {C.WIDTH}x{C.HEIGHT} RGB LED matrix \
(Raspberry Pi 4). Each module is one file that follows this contract exactly:

```python
NAME = "short_name"   # a-z, 0-9, _ ; 2-40 chars, starts with a letter
DURATION = 30         # seconds, {C.DURATION_MIN}-{C.DURATION_MAX} (20-60 is typical)
FPS = 20              # integer {C.FPS_MIN}-{C.FPS_MAX}

def init(w, h):
    \"\"\"Called once. Returns the state as a dict. No I/O.\"\"\"

def render(state, t):
    \"\"\"Returns a numpy array of shape ({C.HEIGHT}, {C.WIDTH}, 3), dtype uint8, RGB.
    t = time in seconds. Pure function: the result depends only on state and t.\"\"\"
```

Rules:
- Allowed imports only: {", ".join(sorted(C.ALLOWED_IMPORTS))}. Nothing else.
- Forbidden: open, exec, eval, compile, __import__, getattr/setattr, globals, any \
__dunder__ name or attribute, os, sys, subprocess, socket, files, network, print-debugging, \
file I/O in numpy/PIL (save, load, open, show).
- Top level of the module may contain only imports, constants and function definitions.
- render must be pure and deterministic: the same t must always give the same frame. Never \
modify state inside render, no global/nonlocal. If you need randomness, create it in init \
with a fixed seed (np.random.default_rng(seed)) and store the arrays in state.
- No loops over individual pixels. Use vectorized numpy (np.mgrid, np.sin, np.where, \
broadcasting). Loops over a small number of objects (e.g. 30 particles) are fine.
- Performance budget: render must take at most {int(C.RENDER_BUDGET_FRACTION * 100)} % of the \
frame time on a Raspberry Pi 4 (at 20 FPS that is 20 ms). Precompute grids in init.
- Visual style: {C.WIDTH}x{C.HEIGHT} is tiny. No 1-pixel details, high contrast, dark \
background, saturated colors. Must visibly move. Loop seamlessly (use periods that divide \
DURATION) or have a meaningful ending.
- Output linear RGB 0-255. Do NOT apply gamma or brightness, the player does that.
- Original designs only: no copyrighted characters, logos or brand imagery.

Example of a valid module:

```python
{EXAMPLE.strip()}
```

Answer with ONLY the code in a single ```python block. No explanations."""


THEMES = [
    "polar aurora waving over a dark horizon",
    "campfire flames with rising sparks",
    "rain drops making ripples on a dark pond",
    "starfield warp speed tunnel",
    "lava lamp with slowly merging blobs",
    "fireworks bursting and fading",
    "ocean waves at sunset",
    "bouncing glowing balls leaving trails",
    "rotating kaleidoscope pattern",
    "spiral galaxy slowly rotating",
    "DNA double helix rotating",
    "gentle snowfall over a dark blue night",
    "heartbeat line on a green monitor",
    "endless neon tunnel",
    "metaballs in neon colors",
    "rotating wireframe 3D cube",
    "neon city skyline with blinking windows",
    "pulsing mandala",
    "aquarium with a few simple fish and bubbles",
    "analog clock with glowing hands",
    "falling green code rain",
    "sunrise over hills",
    "pendulum wave of colored dots",
    "breathing color gradient",
    "lightning storm over the sea",
    "fireflies in a dark forest",
    "radar sweep with blips",
    "concentric color rings expanding from the center",
    "rotating planet with orbiting moon",
    "sand dunes with moving shadows",
    "spinning vinyl record with light reflections",
    "jellyfish floating up in deep sea",
]


def random_theme(rng=random):
    return rng.choice(THEMES)


def initial_prompt(idea):
    return f"Create an animation: {idea}"


def repair_prompt(idea, code, errors):
    err = "\n".join(f"- {e}" for e in errors)
    return (f"Create an animation: {idea}\n\n"
            f"Your previous code failed validation:\n{err}\n\n"
            f"Previous code:\n```python\n{code}\n```\n\n"
            "Fix all the problems and return the complete corrected module.")


_THINK_RE = re.compile(r"<think>.*?</think>", re.S)
_BLOCK_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.S)


def extract_code(text):
    """Vytahne kod z odpovedi (nejdelsi ```python blok). None = zadny kod.

    Premysleni modelu se zahodi: <think>...</think>, a u modelu, ktere
    uvodni <think> vynechavaji, vse pred poslednim </think>.
    """
    text = _THINK_RE.sub("", text or "")
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    blocks = _BLOCK_RE.findall(text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    if "def render" in text and "```" not in text:
        return text.strip() + "\n"
    return None
