#!/usr/bin/env python3
"""Demo 2 pro Waveshare RGB-Matrix 64x64: modre pozadi, padajici vlocky,
jednou za 20 s preleti zeleny drak.

Spusteni na Raspberry Pi:
    sudo python3 demo2.py
"""
import argparse
import math
import random
import time

from PIL import Image, ImageDraw
from rgbmatrix import RGBMatrix, RGBMatrixOptions

SIZE = 64

# --- NASTAVENI (da se prepsat parametrem z prikazove radky) ---
GPIO_MAPPING = "regular"
SLOWDOWN_GPIO = 2
BRIGHTNESS = 60
ROWS = 64
COLS = 64
CHAIN = 1
NO_HARDWARE_PULSE = True

FLAKES = 28               # pocet vlocek
DRAGON_INTERVAL = 20.0    # drak preleti jednou za tolik sekund
DRAGON_FIRST = 3.0        # prvni prelet po tolika sekundach od startu
DRAGON_DURATION = 7.0     # jak dlouho trva prelet pres displej
DRAGON_SCALE = 2          # zvetseni sprite (pixel -> NxN)

# --- Sprite draka (smerem doprava), mezera/. = pruhledne ---
PALETTE = {
    "G": (0, 200, 40),     # telo
    "D": (0, 110, 25),     # kridla
    "Y": (200, 220, 90),   # bricho
    "E": (255, 230, 0),    # oko
    "R": (255, 60, 0),     # plamen
}
WINGS_UP = [
    "....D.....D",
    "....DD...DD",
    ".....DDDDD",
    "..G..GGGGGG....GGG",
    ".GGGGGGGGGGGGGGGGEGGRR",
    "GGYYYYYYYYYGGGGGGGGR",
    "G.GGGGGGGGG..GGG",
    "",
    "",
    "",
]
WINGS_DOWN = [
    "",
    "",
    "",
    "..G..GGGGGG....GGG",
    ".GGGGGGGGGGGGGGGGEGGRR",
    "GGYYYYYYYYYGGGGGGGGR",
    "G..DDDGGGGG..GGG",
    "....DDDDDD",
    "...DD....DD",
    "..DD......DD",
]


def build_sprite(rows):
    w = max(len(r) for r in rows)
    img = Image.new("RGBA", (w, len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in PALETTE:
                img.putpixel((x, y), PALETTE[ch] + (255,))
    return img.resize((w * DRAGON_SCALE, len(rows) * DRAGON_SCALE), Image.NEAREST)


def make_background():
    """Modry prechod: tmavsi nahore, svetlejsi dole."""
    bg = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(bg)
    for y in range(SIZE):
        k = y / (SIZE - 1)
        d.line([(0, y), (SIZE, y)], fill=(0, int(20 + 40 * k), int(90 + 110 * k)))
    return bg


class Flake:
    def __init__(self, random_y=True):
        self.reset(random_y)

    def reset(self, random_y=False):
        self.x = random.uniform(0, SIZE)
        self.y = random.uniform(0, SIZE) if random_y else random.uniform(-6, 0)
        self.speed = random.uniform(6, 16)          # px/s
        self.phase = random.uniform(0, 6.28)
        self.big = random.random() < 0.25

    def update(self, dt, t):
        self.y += self.speed * dt
        self.x += math.sin(t * 1.5 + self.phase) * 4 * dt
        if self.y > SIZE + 2:
            self.reset()

    def draw(self, d):
        x, y = int(self.x) % SIZE, int(self.y)
        if self.big:
            c = (255, 255, 255)
            d.point([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=c)
        else:
            d.point((x, y), fill=(220, 235, 255))


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--gpio-mapping", default=GPIO_MAPPING)
    p.add_argument("--slowdown-gpio", type=int, default=SLOWDOWN_GPIO)
    p.add_argument("--brightness", type=int, default=BRIGHTNESS)
    p.add_argument("--rows", type=int, default=ROWS)
    p.add_argument("--cols", type=int, default=COLS)
    p.add_argument("--chain", type=int, default=CHAIN)
    p.add_argument("--led-no-hardware-pulse", dest="no_hw_pulse", action="store_true",
                   default=NO_HARDWARE_PULSE)
    return p.parse_args()


def main():
    args = parse_args()
    opts = RGBMatrixOptions()
    opts.rows = args.rows
    opts.cols = args.cols
    opts.chain_length = args.chain
    opts.hardware_mapping = args.gpio_mapping
    opts.gpio_slowdown = args.slowdown_gpio
    opts.brightness = args.brightness
    opts.disable_hardware_pulsing = args.no_hw_pulse
    matrix = RGBMatrix(options=opts)
    canvas = matrix.CreateFrameCanvas()

    background = make_background()
    flakes = [Flake() for _ in range(FLAKES)]
    sprites = [build_sprite(WINGS_UP), build_sprite(WINGS_DOWN)]
    sw, sh = sprites[0].size

    start = last = time.time()
    next_dragon = start + DRAGON_FIRST
    dragon_t0 = None
    dragon_y = 20

    try:
        while True:
            now = time.time()
            dt, last = now - last, now
            t = now - start

            frame = background.copy()
            d = ImageDraw.Draw(frame)
            for f in flakes:
                f.update(dt, t)
                f.draw(d)

            if dragon_t0 is None and now >= next_dragon:
                dragon_t0 = now
                dragon_y = random.randint(4, SIZE - sh - 8)
                next_dragon += DRAGON_INTERVAL
            if dragon_t0 is not None:
                k = (now - dragon_t0) / DRAGON_DURATION
                if k >= 1:
                    dragon_t0 = None
                else:
                    x = int(-sw + k * (SIZE + sw))
                    y = int(dragon_y + 4 * math.sin(k * 12))   # vlnity let
                    sprite = sprites[int(now * 6) % 2]          # mavani kridly
                    frame.paste(sprite, (x, y), sprite)

            canvas.SetImage(frame)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.02)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
