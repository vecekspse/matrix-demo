#!/usr/bin/env python3
"""Demo 4 pro Waveshare RGB-Matrix 64x64: tancici Gragas (League of Legends).

Tlusty vousaty Gragas s rudymi vlasy a sudem poskakuje v rytmu, houpe se,
stridave zvedá ruce a nohy. Temne purpurove pozadi mirne pulzuje a jednou za
8 s probehne kratky "horror" glitch (posun radku, cervene oci).

Spusteni na Raspberry Pi:
    sudo python3 demo4.py
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

BEATS_PER_SEC = 1.5       # tempo tance
GLITCH_EVERY = 8.0        # horror glitch jednou za tolik sekund
GLITCH_LEN = 0.25         # jak dlouho trva

# --- Barvy ---
SKIN = (235, 170, 130)
SKIN_D = (200, 130, 95)
HAIR = (190, 55, 15)
BEARD = (215, 85, 20)
PANTS = (60, 70, 140)
BELT = (90, 50, 20)
BOOT = (50, 30, 20)
BARREL = (150, 90, 40)
HOOP = (70, 70, 80)
EYE = (10, 10, 10)


def draw_gragas(d, t, glitch):
    p = t * 2 * math.pi * BEATS_PER_SEC
    s = math.sin(p)
    bob = int(abs(math.sin(p)) * 3)           # poskakovani
    sx = int(round(s * 3))                    # houpani do stran
    cx = 32
    ux = cx + sx                              # stred horni casti tela
    lx = cx + sx // 2                         # stred dolni casti

    # nohy (stridave zvedane) + boty
    for side, up in ((-1, s > 0), (1, s <= 0)):
        lift = 3 if up else 0
        x0 = lx + (-10 if side < 0 else 2)
        d.rectangle([x0, 50, x0 + 7, 57 - lift], fill=PANTS)
        d.ellipse([x0 - 2, 56 - lift, x0 + 9, 61 - lift], fill=BOOT)

    # bricho
    d.ellipse([ux - 15, 24 - bob, ux + 15, 50 - bob], fill=SKIN)
    d.arc([ux - 15, 24 - bob, ux + 15, 50 - bob], 20, 160, fill=SKIN_D)
    d.point((ux, 40 - bob), fill=SKIN_D)      # pupek

    # kalhoty + opasek
    d.rectangle([lx - 13, 46 - bob, lx + 13, 52], fill=PANTS)
    d.rectangle([lx - 13, 45 - bob, lx + 13, 47 - bob], fill=BELT)
    d.point((lx, 46 - bob), fill=(255, 220, 60))

    # leva ruka (stridave nahoru/dolu)
    arm_up = s > 0
    hx, hy = (ux - 23, 14 - bob) if arm_up else (ux - 21, 40 - bob)
    d.line([(ux - 14, 28 - bob), (hx, hy)], fill=SKIN, width=5)
    d.ellipse([hx - 3, hy - 3, hx + 3, hy + 3], fill=SKIN)

    # prava ruka se sudem
    hx2, hy2 = (ux + 21, (30 if arm_up else 18) - bob)
    d.line([(ux + 14, 28 - bob), (hx2, hy2)], fill=SKIN, width=5)
    bx, by = min(hx2 + 2, 56), hy2 - 5
    d.ellipse([bx - 6, by - 8, bx + 6, by + 8], fill=BARREL)
    d.line([(bx - 6, by - 3), (bx + 6, by - 3)], fill=HOOP)
    d.line([(bx - 6, by + 3), (bx + 6, by + 3)], fill=HOOP)
    d.ellipse([hx2 - 3, hy2 - 3, hx2 + 3, hy2 + 3], fill=SKIN)

    # hlava: vlasy, oblicej, vousy
    hy_c = 14 - bob
    d.ellipse([ux - 9, hy_c - 11, ux + 9, hy_c + 2], fill=HAIR)
    d.ellipse([ux - 7, hy_c - 6, ux + 7, hy_c + 9], fill=SKIN)
    d.ellipse([ux - 10, hy_c + 1, ux + 10, hy_c + 19], fill=BEARD)       # plnovous
    d.ellipse([ux - 6, hy_c + 2, ux + 6, hy_c + 6], fill=BEARD)          # knir
    d.rectangle([ux - 2, hy_c + 9, ux + 2, hy_c + 10], fill=(120, 20, 20))  # usta
    eye = (255, 30, 30) if glitch else EYE
    d.rectangle([ux - 4, hy_c - 2, ux - 3, hy_c - 1], fill=eye)
    d.rectangle([ux + 3, hy_c - 2, ux + 4, hy_c - 1], fill=eye)
    d.line([(ux - 5, hy_c - 4), (ux - 2, hy_c - 3)], fill=HAIR)          # oboci
    d.line([(ux + 5, hy_c - 4), (ux + 2, hy_c - 3)], fill=HAIR)


def make_frame(t):
    pulse = 0.85 + 0.15 * math.sin(t * 3)
    glitch = (t % GLITCH_EVERY) < GLITCH_LEN
    bg = (int(45 * pulse) + (40 if glitch else 0), 8, int(60 * pulse))
    img = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 59, SIZE, SIZE], fill=(18, 4, 24))                    # podlaha
    d.line([(0, 59), (SIZE, 59)], fill=(90, 20, 70))
    draw_gragas(d, t, glitch)

    if glitch:                                                           # posun radku
        for y in range(0, SIZE, 2):
            if random.random() < 0.35:
                shift = random.randint(-4, 4)
                row = img.crop((0, y, SIZE, y + 2))
                img.paste(row, (shift, y))
    return img


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

    start = time.time()
    try:
        while True:
            canvas.SetImage(make_frame(time.time() - start))
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.02)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
