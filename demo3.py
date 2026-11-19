#!/usr/bin/env python3
"""Demo 3 pro Waveshare RGB-Matrix 64x64: Nyan Cat.

Poptart kocka s ruzovou polevou a posypkou, seda hlava s usima a tvari,
mavajici ocas, tapkajici nohy, vlnici se duha a blikajici hvezdy na tmave modre.

Spusteni na Raspberry Pi:
    sudo python3 demo3.py
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

FPS_ANIM = 12             # snimku animace kocky za sekundu (originalni gif ~ 12)
STARS = 16                # pocet hvezd
STAR_SPEED = 28.0         # rychlost hvezd (px/s) doleva
CAT_X = 28                # pozice kocky na displeji
CAT_Y = 22

# --- Barvy (originalni paleta Nyan Cat) ---
BG = (0, 51, 102)
K = (0, 0, 0)              # obrys
T = (255, 204, 153)        # kura poptartu
P = (255, 153, 255)        # poleva
S = (255, 51, 153)         # posypka
G = (153, 153, 153)        # seda srst
C = (255, 153, 153)        # tvaricky
W = (255, 255, 255)
RAINBOW = [
    (255, 0, 0),           # cervena
    (255, 153, 0),         # oranzova
    (255, 255, 0),         # zluta
    (51, 255, 0),          # zelena
    (0, 153, 255),         # modra
    (102, 51, 255),        # fialova
]

SPR_W, SPR_H = 26, 20

HEAD = [
    ".KK......KK.",
    ".KGK....KGK.",
    ".KGGKKKKGGK.",
    "KGGGGGGGGGGK",
    "KGGGGGGGGGGK",
    "KGGKWGGGKWGK",
    "KGGKKGGGKKGK",
    "KCCGGGGGGCCK",
    "KCCGKGGKGCCK",
    "KGGGGKKGGGGK",
    ".KGGGGGGGGK.",
    "..KKKKKKKK..",
]
TAIL_A = ["KK..", "KGK.", ".KGK", "..KK"]
TAIL_B = ["..KK", ".KGK", "KGK.", "KK.."]
FOOT = ["KKKK", "KGGK", "KKKK"]
HEAD_PAL = {"K": K, "G": G, "W": W, "C": C}

SPRINKLES = [(8, 5), (12, 5), (15, 6), (7, 8), (10, 8), (8, 11), (11, 11), (6, 6)]


def blit(img, rows, x0, y0):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in HEAD_PAL:
                img.putpixel((x0 + x, y0 + y), HEAD_PAL[ch] + (255,))


def fill(img, x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            img.putpixel((x, y), color + (255,))


def clear_px(img, pts):
    for p in pts:
        img.putpixel(p, (0, 0, 0, 0))


def make_cat(frame):
    """Vykresli kocku (bez duhy) pro dany snimek animace. Vraci RGBA sprite."""
    img = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0))
    dy = 1 if (frame // 3) % 2 else 0          # kocka se mirne houpe
    step = (frame // 3) % 2                    # faze chuze / ocasu

    # ocas (za poptartem)
    blit(img, TAIL_A if step == 0 else TAIL_B, 0, 8 + dy)

    # nohy (zadni vys, predni nize; tapkaji)
    for fx in (5, 10):
        blit(img, FOOT, fx + step, 16)
    for fx in (15, 20):
        blit(img, FOOT, fx + (1 - step), 17)

    # poptart
    fill(img, 3, 1 + dy, 19, 15 + dy, K)
    clear_px(img, [(3, 1 + dy), (19, 1 + dy), (3, 15 + dy), (19, 15 + dy)])
    fill(img, 4, 2 + dy, 18, 14 + dy, T)
    fill(img, 6, 4 + dy, 16, 12 + dy, P)
    clear_px(img, [])
    for p in [(6, 4 + dy), (16, 4 + dy), (6, 12 + dy), (16, 12 + dy)]:
        img.putpixel(p, T + (255,))
    # posypka (polovina bliká)
    for i, (sx, sy) in enumerate(SPRINKLES):
        if (i + frame // 2) % 2 == 0:
            img.putpixel((sx, sy + dy), S + (255,))

    # hlava
    blit(img, HEAD, 13, 6 + dy)
    return img


def make_background():
    return Image.new("RGB", (SIZE, SIZE), BG)


class Star:
    def __init__(self):
        self.x = random.uniform(0, SIZE)
        self.y = random.randint(1, SIZE - 2)
        self.phase = random.uniform(0, 6)
        self.speed = STAR_SPEED * random.uniform(0.7, 1.3)

    def update(self, dt):
        self.x -= self.speed * dt
        if self.x < -3:
            self.x = SIZE + 3
            self.y = random.randint(1, SIZE - 2)

    def draw(self, d, t):
        stage = int(t * 8 + self.phase) % 6
        x, y = int(self.x), self.y
        if stage == 0 or stage == 4:
            d.point((x, y), fill=W)
        elif stage == 1 or stage == 3:
            d.point([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=W)
        elif stage == 2:
            d.point([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
                     (x - 2, y), (x + 2, y), (x, y - 2), (x, y + 2)], fill=W)
        # stage 5: hvezda zhasnuta


def draw_rainbow(d, frame, cat_dy):
    flip = (frame // 3) % 2
    x_end = CAT_X + 6
    for x in range(0, x_end):
        wave = (((x // 4) % 2) ^ flip)
        for i, color in enumerate(RAINBOW):
            y = CAT_Y + 3 + cat_dy + wave + i * 2
            d.line([(x, y), (x, y + 1)], fill=color)


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
    stars = [Star() for _ in range(STARS)]
    cats = [make_cat(f) for f in range(12)]

    start = last = time.time()
    try:
        while True:
            now = time.time()
            dt, last = now - last, now
            t = now - start
            frame = int(t * FPS_ANIM) % 12
            cat_dy = 1 if (frame // 3) % 2 else 0

            img = background.copy()
            d = ImageDraw.Draw(img)
            for s in stars:
                s.update(dt)
                s.draw(d, t)
            draw_rainbow(d, frame, cat_dy)
            cat = cats[frame]
            img.paste(cat, (CAT_X, CAT_Y), cat)

            canvas.SetImage(img)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.01)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
