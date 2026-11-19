# RGB Matrix 64x64 test

Pulsující červené srdce + bílý scrollující text "SPŠE a VOŠ Pardubice" (Waveshare RGB-Matrix 64x64, Raspberry Pi).

```bash
git clone <url-repa> && cd <repo>
sudo python3 matrix_demo.py
```

Pokud nesedí zapojení/obraz bliká, zkus parametry:

```bash
sudo python3 matrix_demo.py --gpio-mapping adafruit-hat --slowdown-gpio 3 --brightness 50
```

Vyžaduje knihovnu `rgbmatrix` (hzeller/rpi-rgb-led-matrix) a Pillow (`sudo apt install python3-pil`).
