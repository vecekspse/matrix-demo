#!/usr/bin/env python3
"""Test pro Waveshare RGB-Matrix 64x64: pulsujici cervene srdce + bily scrollujici text.

Spusteni na Raspberry Pi (kvuli GPIO s sudo):
    sudo python3 matrix_demo.py
    sudo python3 matrix_demo.py --gpio-mapping adafruit-hat --slowdown-gpio 2
"""
import argparse
import math
import time

from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions

TEXT = "SPŠE a VOŠ Pardubice"
SIZE = 64

# --- NASTAVENI (zde uprav; da se prepsat i parametrem z prikazove radky) ---
GPIO_MAPPING = "regular"   # regular | adafruit-hat | adafruit-hat-pwm ...
SLOWDOWN_GPIO = 2          # pri blikani zkus 3 nebo 4
BRIGHTNESS = 60            # 1-100
ROWS = 64
COLS = 64
CHAIN = 1
SPEED = 30.0               # rychlost textu v px/s
NO_HARDWARE_PULSE = True   # = --led-no-hardware-pulse (neni potreba vypinat zvuk)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_text_strip(text, height=18, gap=24):
    """Vyrenderuje text do jednoho dlouheho pasu (s mezerou pro plynuly cyklus)."""
    font = load_font(13)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    width = int(probe.textlength(text, font=font))
    strip = Image.new("RGB", (width + gap, height), (0, 0, 0))
    ImageDraw.Draw(strip).text((0, height // 2), text, font=font, fill=(255, 255, 255), anchor="lm")
    return strip


def heart_points(cx, cy, scale):
    pts = []
    for i in range(60):
        t = 2 * math.pi * i / 60
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * scale, cy - y * scale))
    return pts


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--gpio-mapping", default=GPIO_MAPPING)
    p.add_argument("--slowdown-gpio", type=int, default=SLOWDOWN_GPIO)
    p.add_argument("--brightness", type=int, default=BRIGHTNESS)
    p.add_argument("--rows", type=int, default=ROWS)
    p.add_argument("--cols", type=int, default=COLS)
    p.add_argument("--chain", type=int, default=CHAIN)
    p.add_argument("--speed", type=float, default=SPEED)
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

    strip = make_text_strip(TEXT)
    strip_w, strip_h = strip.size
    text_y = SIZE - strip_h - 2

    start = time.time()
    try:
        while True:
            t = time.time() - start
            # tep ~ 1,2 Hz, 0..1
            beat = (math.sin(t * 2 * math.pi * 1.2) + 1) / 2
            scale = 0.60 + 0.30 * beat
            red = int(120 + 135 * beat)

            frame = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
            ImageDraw.Draw(frame).polygon(heart_points(32, 20, scale), fill=(red, 0, 0))

            # plynule scrollovani textu zprava doleva ve smycce
            offset = int(t * args.speed) % strip_w
            x = SIZE - offset
            while x < SIZE:
                if x + strip_w > 0:
                    frame.paste(strip, (x, text_y))
                x += strip_w
            # druha kopie pro navazani
            frame.paste(strip, (SIZE - offset - strip_w, text_y))

            canvas.SetImage(frame)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.02)
    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
