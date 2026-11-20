#!/usr/bin/env python3
"""Prehravac animaci z library/ na LED matici 64x64.

JEDINE misto v projektu, kde se importuje rgbmatrix.

- Hraje jen animace z library/, ktere maji <name>.json s validation.ok = true.
- Vybira nahodne a nepousti stejnou animaci dvakrat po sobe.
- Kazda animace bezi v izolovanem podprocesu (runner/validate.py, rezim serve).
  Pri padu nebo timeoutu se prejde na dalsi animaci.
- Snimky se casuji podle realneho casu; kdyz je render pomaly, snimky se
  vynechaji, animace se nezpomaluje.
- Gamma (LUT) se aplikuje tady, jas nastavuje hardware matice.

Spusteni na Raspberry Pi (pozor na spravny interpret pri sudo):
    sudo .venv/bin/python -m runner.player
    sudo .venv/bin/python -m runner.player --brightness 40 --slowdown-gpio 2

Test na PC bez matice:
    .venv/bin/python -m runner.player --no-matrix --max-seconds 5
"""
import argparse
import collections
import json
import os
import random
import select
import signal
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from runner import contract as C  # noqa: E402
from runner.validate import FRAME_BYTES, popen_serve, static_check  # noqa: E402

# --- NASTAVENI DISPLEJE (prevzato z matrix_demo.py; da se prepsat parametrem) ---
GPIO_MAPPING = "regular"
SLOWDOWN_GPIO = 4          # Pi 4: >= 4 (dema mela 2; pri potizich zkus --slowdown-gpio 2)
BRIGHTNESS = 60            # 1-100, pro trvaly provoz 30-60
ROWS = 64
COLS = 64
CHAIN = 1
NO_HARDWARE_PULSE = True   # = --led-no-hardware-pulse (neni potreba vypinat zvuk)
PWM_BITS = None            # None = vychozi hodnota knihovny

GAMMA = 2.2
LIBRARY = ROOT / "library"

INIT_TIMEOUT_S = 15.0      # start podprocesu + import numpy + init()
FRAME_TIMEOUT_S = 2.0      # jeden render(); delsi = animace se zasekla
FAIL_PAUSE_S = 1.0         # po chybe chvili tma (aby se nezacyklilo na padajicich)
EMPTY_PAUSE_S = 5.0        # prazdna knihovna -> zkusit znovu za chvili


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Displej
# --------------------------------------------------------------------------

class FakeMatrix:
    """Nahrada matice pro test na PC (--no-matrix)."""

    class _Canvas:
        def SetImage(self, img, *a, **kw):
            pass

        def Clear(self):
            pass

    def CreateFrameCanvas(self):
        return self._Canvas()

    def SwapOnVSync(self, canvas, *a, **kw):
        return canvas

    def Clear(self):
        pass


def open_matrix(args, gamma):
    if args.no_matrix:
        return FakeMatrix()
    if args.web:
        from runner.webview import WebMatrix
        return WebMatrix(args.web)
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    opts = RGBMatrixOptions()
    opts.rows = args.rows
    opts.cols = args.cols
    opts.chain_length = args.chain
    opts.hardware_mapping = args.gpio_mapping
    opts.gpio_slowdown = args.slowdown_gpio
    opts.brightness = args.brightness
    opts.disable_hardware_pulsing = args.no_hw_pulse
    if args.pwm_bits is not None:
        opts.pwm_bits = args.pwm_bits
    # Prehravac zustava root, aby mohl cist library/ v domovskem adresari;
    # podprocesy s animacemi se samy prepinaji na uzivatele nobody.
    if hasattr(opts, "drop_privileges"):
        opts.drop_privileges = False
    matrix = RGBMatrix(options=opts)
    # Gamma resi nase LUT – vestavenou korekci knihovny vypneme, at se nezdvoji.
    if gamma > 0 and hasattr(matrix, "luminanceCorrect"):
        matrix.luminanceCorrect = False
    return matrix


def gamma_lut(gamma):
    x = np.arange(256, dtype=np.float64) / 255.0
    if gamma <= 0:
        return (x * 255).round().astype(np.uint8)
    return (255 * x ** gamma).round().astype(np.uint8)


# --------------------------------------------------------------------------
# Knihovna
# --------------------------------------------------------------------------

def scan_library(lib_dir):
    """Animace s metadaty a uspesnou validaci."""
    found = []
    for py in sorted(lib_dir.glob("*.py")):
        try:
            meta = json.loads(py.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and meta.get("validation", {}).get("ok"):
            found.append(py)
    return found


def pick_next(candidates, last):
    choices = [p for p in candidates if p != last] or candidates
    return random.choice(choices)


# --------------------------------------------------------------------------
# Podproces s animaci
# --------------------------------------------------------------------------

def _read_exact(fd, n, timeout):
    """Precte presne n bajtu, nebo vrati None pri timeoutu / EOF."""
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while len(buf) < n:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            return None
        chunk = os.read(fd, n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def _drain(stream, tail):
    """Cte stderr podprocesu (aby se roura nezaplnila), drzi posledni radky."""
    for line in iter(stream.readline, b""):
        tail.append(line.decode("utf-8", "replace").rstrip())
    stream.close()


def _stop(proc, drain_thread):
    try:
        proc.stdin.close()
    except OSError:
        pass
    try:
        proc.wait(timeout=1)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()
    proc.stdout.close()
    drain_thread.join(timeout=1)


class AnimationFailed(Exception):
    pass


def play(path, display, lut, max_seconds=None):
    """Prehraje jednu animaci. Vraci statistiku, pri chybe AnimationFailed."""
    source = path.read_text(encoding="utf-8")
    errors, _ = static_check(source)            # soubor se mohl po validaci zmenit
    if errors:
        raise AnimationFailed("statická kontrola: " + errors[0])
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    fps = int(meta.get("fps") or meta["validation"]["fps"])
    duration = float(meta.get("duration") or meta["validation"]["duration"])
    duration = min(duration, C.DURATION_MAX, max_seconds or C.DURATION_MAX)

    proc = popen_serve(source, str(path), cpu_s=int(duration) + 30)
    tail = collections.deque(maxlen=20)
    drain = threading.Thread(target=_drain, args=(proc.stderr, tail), daemon=True)
    drain.start()
    fd = proc.stdout.fileno()

    def fail(reason):
        detail = f" | {tail[-1]}" if tail else ""
        return AnimationFailed(f"{reason}{detail}")

    shown = skipped = 0
    wait_ms = []
    try:
        if _read_exact(fd, 1, INIT_TIMEOUT_S) != b"R":
            _stop(proc, drain)
            raise fail("init() selhal nebo nestihl limit")
        start = time.monotonic()
        k = 0
        while True:
            t = k / fps
            if t >= duration:
                break
            t0 = time.monotonic()
            try:
                proc.stdin.write(struct.pack("<d", t))
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                _stop(proc, drain)
                raise fail(f"podproces skončil (t={t:.2f})")
            data = _read_exact(fd, FRAME_BYTES, FRAME_TIMEOUT_S)
            if data is None:
                try:
                    proc.wait(timeout=0.5)          # EOF -> proces prave konci
                    crashed = True
                except subprocess.TimeoutExpired:
                    crashed = False
                _stop(proc, drain)
                if crashed:
                    raise fail(f"render spadl (t={t:.2f})")
                raise fail(f"render se zasekl, nestihl {FRAME_TIMEOUT_S} s (t={t:.2f})")
            wait_ms.append((time.monotonic() - t0) * 1000)

            frame = lut[np.frombuffer(data, dtype=np.uint8).reshape(C.FRAME_SHAPE)]
            display.set_image(Image.fromarray(frame, "RGB"))
            delay = start + t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            display.swap()
            shown += 1

            # dalsi snimek = prvni casovy slot v budoucnosti (pomaly render -> vynechat)
            nk = max(k + 1, int((time.monotonic() - start) * fps) + 1)
            skipped += nk - k - 1
            k = nk
    except BaseException:
        if proc.poll() is None:
            _stop(proc, drain)
        raise
    _stop(proc, drain)
    mean_ms = sum(wait_ms) / len(wait_ms) if wait_ms else 0.0
    return {"shown": shown, "skipped": skipped, "mean_frame_ms": round(mean_ms, 2)}


class Display:
    def __init__(self, matrix):
        self.matrix = matrix
        self.canvas = matrix.CreateFrameCanvas()

    def set_image(self, img):
        self.canvas.SetImage(img)

    def swap(self):
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def black(self):
        self.canvas.Clear()
        self.swap()


# --------------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Přehrávač animací z library/ na LED matici.")
    p.add_argument("--gpio-mapping", default=GPIO_MAPPING)
    p.add_argument("--slowdown-gpio", type=int, default=SLOWDOWN_GPIO)
    p.add_argument("--brightness", type=int, default=BRIGHTNESS)
    p.add_argument("--rows", type=int, default=ROWS)
    p.add_argument("--cols", type=int, default=COLS)
    p.add_argument("--chain", type=int, default=CHAIN)
    p.add_argument("--pwm-bits", type=int, default=PWM_BITS)
    p.add_argument("--led-no-hardware-pulse", dest="no_hw_pulse", action="store_true",
                   default=NO_HARDWARE_PULSE)
    p.add_argument("--gamma", type=float, default=GAMMA,
                   help="gamma korekce (0 = vypnout a nechat korekci knihovny)")
    p.add_argument("--library", type=Path, default=LIBRARY)
    p.add_argument("--max-seconds", type=float, default=None,
                   help="zkrátit každou animaci (pro testy)")
    p.add_argument("--max-total", type=float, default=None,
                   help="ukončit po tolika sekundách (pro testy)")
    p.add_argument("--no-matrix", action="store_true", help="bez displeje (test na PC)")
    p.add_argument("--web", type=int, metavar="PORT", default=None,
                   help="místo matice zobrazit v prohlížeči na http://localhost:PORT (PC)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.web:
        args.gamma = 0          # monitor ma vlastni gammu, LUT by obraz ztmavil
    lut = gamma_lut(args.gamma)
    matrix = open_matrix(args, args.gamma)
    display = Display(matrix)
    if args.web:
        log(f"virtuální matice: http://localhost:{args.web}")

    def on_term(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_term)

    begin = time.monotonic()
    last = None
    try:
        while args.max_total is None or time.monotonic() - begin < args.max_total:
            candidates = scan_library(args.library)
            if not candidates:
                log(f"knihovna {args.library} je prázdná, čekám")
                display.black()
                time.sleep(EMPTY_PAUSE_S)
                continue
            path = pick_next(candidates, last)
            last = path
            log(f"▶ {path.stem}")
            if hasattr(matrix, "label"):
                matrix.label = path.stem
            try:
                stats = play(path, display, lut, args.max_seconds)
                log(f"  ok {stats}")
            except Exception as e:             # nic nesmi zastavit prehravani
                log(f"  ✗ {path.stem}: {type(e).__name__}: {e}")
                display.black()
                time.sleep(FAIL_PAUSE_S)
    except KeyboardInterrupt:
        pass
    finally:
        matrix.Clear()
        log("konec, matice zhasnuta")
    return 0


if __name__ == "__main__":
    sys.exit(main())
