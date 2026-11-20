#!/usr/bin/env python3
"""Generovani na pozadi: jednou za --interval vytvori novou animaci.

Bezi jako samostatny proces vedle prehravace. Prehravac na nem nezavisi,
hraje z library/ a nove animace si najde sam.

- Kdyz ma knihovna --max-library animaci, generator jen ceka.
- Docasna chyba (sit, AI stroj nejede) -> pocka a zkusi znovu.
- Chyba konfigurace/klice za behu -> pocka dele (FATAL_PAUSE_S).
- Temata vybira nahodne a prednostne ta, ktera v knihovne jeste nejsou.

Pouziti:
    python -m generator.loop                          # backend z GENERATOR_BACKEND
    python -m generator.loop --backend openai --interval 300 --max-library 80
"""
import argparse
import json
import os
import random
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generator import generate as G  # noqa: E402
from generator import prompt as P  # noqa: E402
from generator.backends import BackendError, FatalBackendError, make_backend  # noqa: E402

INTERVAL_S = 600         # nova animace jednou za 10 minut
MAX_LIBRARY = 50         # vic animaci v knihovne negenerovat
RETRY_S = 120            # po docasne chybe
FATAL_PAUSE_S = 1800     # po chybe klice/konfigurace za behu

log = G.log


def library_entries():
    """Metadata animaci v knihovne, ktere prosly validaci."""
    out = []
    for js in sorted(G.LIBRARY.glob("*.json")):
        try:
            meta = json.loads(js.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(meta, dict) and meta.get("validation", {}).get("ok")
                and js.with_suffix(".py").exists()):
            out.append(meta)
    return out


def pick_theme(entries):
    used = {m.get("prompt") for m in entries}
    fresh = [t for t in P.THEMES if t not in used]
    return random.choice(fresh or P.THEMES)


def generate_once(backend, idea, attempts):
    """Jedna animace. Vraci True, kdyz pribyla do knihovny."""
    log(f"nápad: {idea}")
    success, code, result, log_, info, text = G.generate_one(backend, idea, attempts)
    if success:
        path = G.save_accepted(code, result, idea, log_, info)
        log(f"  ✓ {G._rel(path)}")
        return True
    reason = log_[-1].get("errors") if log_ else ["žádný pokus"]
    path = G.save_rejected(code, idea, log_, info, text, reason)
    log(f"  ✗ zamítnuto → {G._rel(path)}")
    return False


def sleep(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        time.sleep(min(5.0, end - time.monotonic()))


def main(argv=None):
    p = argparse.ArgumentParser(description="Generování animací na pozadí.")
    p.add_argument("--backend", choices=G.BACKENDS, default=None,
                   help="anthropic | openai (výchozí: GENERATOR_BACKEND z .env)")
    p.add_argument("--model")
    p.add_argument("--effort", default="medium",
                   choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--interval", type=float, default=INTERVAL_S,
                   help=f"sekund mezi animacemi (výchozí {INTERVAL_S})")
    p.add_argument("--max-library", type=int, default=MAX_LIBRARY,
                   help=f"při tolika animacích v knihovně negenerovat (výchozí {MAX_LIBRARY})")
    p.add_argument("--attempts", type=int, default=G.MAX_ATTEMPTS)
    p.add_argument("--max-runs", type=int, default=None, help="skončit po N pokusech (testy)")
    a = p.parse_args(argv)

    G.load_dotenv()
    backend_name = a.backend or os.environ.get("GENERATOR_BACKEND", "").strip()
    if backend_name not in G.BACKENDS:
        log("vyber backend: --backend anthropic | openai "
            "(nebo nastav GENERATOR_BACKEND v .env)")
        return 2
    try:
        backend = make_backend(backend_name, model=a.model, effort=a.effort)
    except FatalBackendError as e:
        log(f"chyba konfigurace: {e}")
        return 2

    def on_term(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_term)

    log(f"smyčka: backend {backend.name}, model {backend.model}, "
        f"každých {a.interval:.0f} s, max {a.max_library} animací")
    runs = 0
    waiting_at = None            # pocet animaci, pri kterem uz jsme hlasili cekani
    try:
        while a.max_runs is None or runs < a.max_runs:
            entries = library_entries()
            if len(entries) >= a.max_library:
                if waiting_at != len(entries):
                    log(f"knihovna má {len(entries)} animací (limit {a.max_library}), čekám")
                    waiting_at = len(entries)
                sleep(a.interval)
                continue
            waiting_at = None
            runs += 1
            t0 = time.monotonic()
            try:
                generate_once(backend, pick_theme(entries), a.attempts)
            except FatalBackendError as e:
                log(f"  chyba klíče/konfigurace: {e} – zkusím za {FATAL_PAUSE_S // 60} min")
                sleep(FATAL_PAUSE_S)
                continue
            except BackendError as e:
                log(f"  AI nedostupná: {e} – zkusím za {RETRY_S} s")
                sleep(RETRY_S)
                continue
            if a.max_runs is not None and runs >= a.max_runs:
                break
            # interval se pocita od zacatku generovani
            sleep(max(0.0, a.interval - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        pass
    log("smyčka ukončena")
    return 0


if __name__ == "__main__":
    sys.exit(main())
