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

## Přehrávač AI animací (`runner/`)

Animace podle kontraktu v `AGENTS.md` leží v `library/` (`<name>.py` + `<name>.json`).
Přehrávač hraje jen ty, které prošly validací, každou v izolovaném podprocesu.

Na PC (vývoj):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m runner.validate library/plasma_ocean.py   # JSON s výsledkem
.venv/bin/python -m runner.preview library/plasma_ocean.py    # previews/plasma_ocean.gif
.venv/bin/python -m runner.player --web 8064                  # virtuální matice na http://localhost:8064
.venv/bin/python -m runner.player --no-matrix --max-seconds 5 # přehrávač bez displeje
```

Na Raspberry Pi (`rgbmatrix` je nainstalovaný systémově, proto venv se system-site-packages):

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt
sudo .venv/bin/python -m runner.player                         # Ctrl+C = zhasnout a konec
sudo .venv/bin/python -m runner.player --brightness 40 --slowdown-gpio 2
```

### Generátor (`generator/`)

```bash
.venv/bin/pip install -r requirements-generator.txt
cp .env.example .env        # doplnit klíč / adresu AI stroje
.venv/bin/python -m generator.generate --backend anthropic --count 20   # nebo GENERATOR_BACKEND v .env
.venv/bin/python -m generator.generate --backend openai --idea "ohňostroj nad městem"
```

Každý nápad: AI napíše modul → validace → při chybě oprava (max. 3 pokusy).
Přijaté jdou do `library/` (`.py` + `.json` s metadaty), zamítnuté do `rejected/` i s důvodem.

### Generování na pozadí

```bash
.venv/bin/python -m generator.loop                       # každých 10 min jedna animace, max. 50 v knihovně
.venv/bin/python -m generator.loop --interval 300 --max-library 80
```

Přehrávač a generátor jsou nezávislé procesy: přehrávač hraje z `library/` a nové animace si najde sám,
když AI nebo síť nejede, hraje dál. Na Pi je spustí jako služby šablony v `deploy/` (návod v jejich hlavičce).
