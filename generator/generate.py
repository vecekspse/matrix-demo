#!/usr/bin/env python3
"""Davkovy generator animaci.

Napad (text nebo nahodne tema) -> AI napise modul -> validace -> pri chybe
oprava (max 3 pokusy) -> library/<name>.py + .json, jinak rejected/.

Klice a adresy se ctou z prostredi nebo ze souboru .env v koreni repa
(.env je v .gitignore, do gitu nepatri):
    ANTHROPIC_API_KEY=...
    OPENAI_BASE_URL=http://ai-stroj:8000/v1
    OPENAI_API_KEY=...            # pokud ho server vyzaduje
    OPENAI_MODEL=nazev-modelu

Pouziti:
    python -m generator.generate --backend anthropic --count 20
    python -m generator.generate --backend openai --idea "ohňostroj nad městem"
    python -m generator.generate --backend openai --model qwen-coder --count 5
"""
import argparse
import datetime
import json
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generator import prompt as P  # noqa: E402
from generator.backends import BackendError, FatalBackendError, make_backend  # noqa: E402
from runner.validate import validate_source  # noqa: E402

LIBRARY = ROOT / "library"
REJECTED = ROOT / "rejected"
MAX_ATTEMPTS = 3
BACKENDS = ["anthropic", "openai"]


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


def load_dotenv(path=ROOT / ".env"):
    """Minimalni .env: KEY=VALUE, komentare #. Existujici promenne neprepisuje."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def _write_atomic(path, text):
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _sum_usage(attempts):
    total = {}
    for a in attempts:
        for k, v in (a.get("usage") or {}).items():
            if isinstance(v, int):
                total[k] = total.get(k, 0) + v
    return total


# --------------------------------------------------------------------------

def generate_one(backend, idea, max_attempts=MAX_ATTEMPTS):
    """Napad -> overeny kod. Pri chybe validace posle AI kod + chyby zpet.

    Vraci (ok, code, validation, attempts, info, last_text). Pri neuspechu je
    code posledni kod, ktery AI vratila (nebo None).
    """
    attempts, code, errors, info, text = [], None, None, {}, ""
    for i in range(1, max_attempts + 1):
        # bez predchoziho kodu znovu od zacatku, jinak oprava
        user = (P.initial_prompt(idea) if code is None
                else P.repair_prompt(idea, code, errors))
        t0 = time.monotonic()
        text, info = backend.complete(P.SYSTEM, user)
        entry = {"attempt": i, "seconds": round(time.monotonic() - t0, 1),
                 "usage": info.get("usage")}
        new_code = P.extract_code(text)
        if new_code is None:
            errors = ["odpověď neobsahuje kód v bloku ```python ... ```"]
            entry.update(ok=False, errors=errors)
            attempts.append(entry)
            log(f"  pokus {i}: bez kódu")
            continue
        code = new_code
        result = validate_source(code, "animation.py")
        entry.update(ok=result["ok"], errors=result["errors"], warnings=result["warnings"],
                     stats=result["stats"])
        attempts.append(entry)
        if result["ok"]:
            log(f"  pokus {i}: OK ({result['stats'].get('mean_ms')} ms/snímek)")
            return True, code, result, attempts, info, text
        errors = result["errors"]
        log(f"  pokus {i}: {len(errors)} chyb – {errors[0][:120]}")
    return False, code, None, attempts, info, text


def unique_name(name):
    """NAME, ktere jeste neni v library/ (plasma -> plasma_2 ...)."""
    if not (LIBRARY / f"{name}.py").exists():
        return name
    n = 2
    while (LIBRARY / f"{name[:36]}_{n}.py").exists():
        n += 1
    return f"{name[:36]}_{n}"


_NAME_LINE = re.compile(r"""^NAME\s*=\s*(["'])[a-z0-9_]+\1""", re.M)


def save_accepted(code, result, idea, attempts, info):
    name = unique_name(result["name"])
    if name != result["name"]:
        code = _NAME_LINE.sub(f'NAME = "{name}"', code, count=1)
    meta = {
        "name": name,
        "prompt": idea,
        "backend": info.get("backend"),
        "model": info.get("model"),
        "created": _now(),
        "fps": result["fps"],
        "duration": result["duration"],
        "mean_frame_ms": result["stats"].get("mean_ms"),
        "attempts": len(attempts),
        "usage": _sum_usage(attempts),
        "attempt_log": attempts,
        "validation": result,
    }
    LIBRARY.mkdir(exist_ok=True)
    # .py prvni, .json az pak: prehravac bere jen animace s .json
    _write_atomic(LIBRARY / f"{name}.py", code)
    _write_atomic(LIBRARY / f"{name}.json",
                  json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return LIBRARY / f"{name}.py"


def save_rejected(code, idea, attempts, info, last_text, reason):
    REJECTED.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", idea.lower())[:40].strip("_") or "napad"
    stem = f"{time.strftime('%Y%m%d-%H%M%S')}_{slug}"
    meta = {
        "prompt": idea,
        "backend": info.get("backend"),
        "model": info.get("model"),
        "created": _now(),
        "reason": reason,
        "attempts": len(attempts),
        "usage": _sum_usage(attempts),
        "attempt_log": attempts,
    }
    if code:
        (REJECTED / f"{stem}.py").write_text(code, encoding="utf-8")
    else:
        meta["last_response"] = (last_text or "")[:4000]
    (REJECTED / f"{stem}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return REJECTED / f"{stem}.json"


# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="Dávkové generování animací pomocí AI.")
    p.add_argument("--backend", choices=BACKENDS, default=None,
                   help="anthropic | openai (výchozí: GENERATOR_BACKEND z .env)")
    p.add_argument("--model", help="výchozí: claude-opus-5-5 / OPENAI_MODEL")
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                   help="jen Anthropic: hloubka přemýšlení (výchozí medium)")
    p.add_argument("--count", type=int, default=None,
                   help="počet animací (výchozí: počet --idea, jinak 1)")
    p.add_argument("--idea", action="append", default=[],
                   help="nápad (lze opakovat); bez něj náhodné téma")
    p.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    a = p.parse_args(argv)

    load_dotenv()
    backend_name = a.backend or os.environ.get("GENERATOR_BACKEND", "").strip()
    if backend_name not in BACKENDS:
        log("vyber backend: --backend anthropic | openai "
            "(nebo nastav GENERATOR_BACKEND v .env)")
        return 2
    count = a.count or len(a.idea) or 1
    ideas = [a.idea[i] if i < len(a.idea) else P.random_theme() for i in range(count)]

    try:
        backend = make_backend(backend_name, model=a.model, effort=a.effort)
    except FatalBackendError as e:
        log(f"chyba konfigurace: {e}")
        return 2
    log(f"backend {backend.name}, model {backend.model}, {count} animací")

    ok = rejected = failed = 0
    for n, idea in enumerate(ideas, 1):
        log(f"[{n}/{count}] {idea}")
        try:
            success, code, result, attempts, info, text = generate_one(backend, idea, a.attempts)
        except FatalBackendError as e:
            log(f"  zastavuji dávku: {e}")
            return 2
        except BackendError as e:
            log(f"  přeskočeno: {e}")
            failed += 1
            continue
        if success:
            path = save_accepted(code, result, idea, attempts, info)
            log(f"  ✓ {_rel(path)}")
            ok += 1
        else:
            reason = attempts[-1].get("errors") if attempts else ["žádný pokus"]
            path = save_rejected(code, idea, attempts, info, text, reason)
            log(f"  ✗ zamítnuto → {_rel(path)}")
            rejected += 1
    log(f"hotovo: {ok} přijato, {rejected} zamítnuto, {failed} chyb backendu")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
