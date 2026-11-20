#!/usr/bin/env python3
"""Validator animaci podle runner/contract.py.

1. Staticka kontrola zdrojaku pres ast (importy, zakazana jmena/atributy,
   povinne konstanty a funkce).
2. Zkusebni beh v podprocesu s limity (pamet, CPU, zadne zapisy do souboru):
   init() + aspon 100 snimku render() offscreen.
3. Kontrola vystupu: tvar, dtype, cas snimku, cerne/staticke snimky, cistota.

Vysledek je JSON {"ok": bool, "errors": [...], "warnings": [...], "stats": {...}}.
Chyby jsou psane tak, aby slouzily jako zpetna vazba pro AI.

POZOR: kontrola pres ast NENI sandbox. Ochranou je az podproces s limity.

Pouziti:
    python -m runner.validate library/plasma_ocean.py
    python -m runner.validate soubor.py --speedup 1     # mereni jako na Pi
"""
import argparse
import ast
import json
import os
import platform
import random
import resource
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:          # podproces bezi s -I, bez cesty k repu
    sys.path.insert(0, str(ROOT))

from runner import contract as C  # noqa: E402

FRAME_BYTES = C.WIDTH * C.HEIGHT * C.CHANNELS


# --------------------------------------------------------------------------
# 1) Staticka kontrola
# --------------------------------------------------------------------------

def _is_dunder(name):
    return name.startswith("__") and name.endswith("__")


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


_DIM_NAMES = {"w", "h", "W", "H", "width", "height", "WIDTH", "HEIGHT", "SIZE", "size"}


def _is_pixel_loop(node):
    """for ... in range(64 | w | h | ...) – cyklus pres radky/sloupce displeje."""
    if not isinstance(node, ast.For):
        return False
    it = node.iter
    if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name)
            and it.func.id == "range" and it.args):
        return False
    for arg in it.args:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Name) and sub.id in _DIM_NAMES:
                return True
            if (isinstance(sub, ast.Constant) and isinstance(sub.value, int)
                    and not isinstance(sub.value, bool) and sub.value >= 32):
                return True
    return False


def _has_nested_pixel_loops(fn):
    for outer in ast.walk(fn):
        if _is_pixel_loop(outer):
            for inner in ast.walk(outer):
                if inner is not outer and _is_pixel_loop(inner):
                    return True
    return False


def _loop_depth(node, depth=0):
    """Nejvetsi hloubka vnoreni for/while cyklu (comprehensions nepocitame)."""
    best = depth
    for child in ast.iter_child_nodes(node):
        d = depth + 1 if isinstance(child, (ast.For, ast.While)) else depth
        best = max(best, _loop_depth(child, d))
    return best


def static_check(source):
    """Vrati (errors, warnings) pro zdrojovy kod animace."""
    errors, warnings = [], []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"Syntaktická chyba na řádku {e.lineno}: {e.msg}"], []

    def err(node, msg):
        line = getattr(node, "lineno", None)
        errors.append(f"řádek {line}: {msg}" if line else msg)

    # --- nejvyssi uroven modulu: jen importy, konstanty, funkce, tridy, docstring
    consts, funcs = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef)):
            continue
        if isinstance(node, ast.FunctionDef):
            funcs[node.name] = node
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for tg in targets:
                if isinstance(tg, ast.Name) and tg.id in C.REQUIRED_CONSTANTS:
                    consts[tg.id] = (node, node.value)
            continue
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue
        err(node, "na nejvyšší úrovni modulu smí být jen importy, konstanty "
                  f"a definice funkcí (nalezeno {type(node).__name__})")

    # --- pruchod celym stromem
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split(".")
                if parts[0] not in C.ALLOWED_IMPORTS:
                    err(node, f"import '{a.name}' není povolen "
                              f"(povoleno: {', '.join(sorted(C.ALLOWED_IMPORTS))})")
                elif any(p in C.FORBIDDEN_ATTRS for p in parts):
                    err(node, f"import '{a.name}' není povolen")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                err(node, "relativní import není povolen")
                continue
            parts = (node.module or "").split(".")
            if parts[0] not in C.ALLOWED_IMPORTS:
                err(node, f"import z '{node.module}' není povolen "
                          f"(povoleno: {', '.join(sorted(C.ALLOWED_IMPORTS))})")
            elif any(p in C.FORBIDDEN_ATTRS for p in parts):
                err(node, f"import z '{node.module}' není povolen")
            for a in node.names:
                if a.name == "*":
                    err(node, "import * není povolen")
                elif a.name in C.FORBIDDEN_ATTRS or a.name in C.FORBIDDEN_NAMES:
                    err(node, f"import '{a.name}' z '{node.module}' není povolen")
        elif isinstance(node, ast.Name):
            if node.id in C.FORBIDDEN_NAMES:
                err(node, f"jméno '{node.id}' je zakázané")
            elif _is_dunder(node.id):
                err(node, f"jméno '{node.id}' je zakázané (žádné __jména__)")
        elif isinstance(node, ast.Attribute):
            if _is_dunder(node.attr):
                err(node, f"atribut '.{node.attr}' je zakázaný (žádné __atributy__)")
            elif node.attr in C.FORBIDDEN_ATTRS:
                err(node, f"atribut '.{node.attr}' je zakázaný (žádné soubory ani I/O)")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            err(node, "global/nonlocal není povolen – render musí být čistá funkce, "
                      "stav patří do dictu z init()")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
            err(node, "async není povolen")

    # --- povinne konstanty
    for name in C.REQUIRED_CONSTANTS:
        if name not in consts:
            errors.append(f"chybí konstanta {name} na nejvyšší úrovni modulu")
    if "NAME" in consts:
        node, val = consts["NAME"]
        v = _literal(val)
        if not isinstance(v, str) or not C.NAME_RE.match(v):
            err(node, "NAME musí být řetězec z malých písmen a-z, číslic a '_' "
                      "(2–40 znaků, začíná písmenem)")
    if "DURATION" in consts:
        node, val = consts["DURATION"]
        v = _literal(val)
        if (not isinstance(v, (int, float)) or isinstance(v, bool)
                or not C.DURATION_MIN <= v <= C.DURATION_MAX):
            err(node, f"DURATION musí být číslo {C.DURATION_MIN}–{C.DURATION_MAX} (sekundy)")
    if "FPS" in consts:
        node, val = consts["FPS"]
        v = _literal(val)
        if not isinstance(v, int) or isinstance(v, bool) or not C.FPS_MIN <= v <= C.FPS_MAX:
            err(node, f"FPS musí být celé číslo {C.FPS_MIN}–{C.FPS_MAX}")

    # --- povinne funkce
    for fname, params in C.REQUIRED_FUNCTIONS.items():
        fn = funcs.get(fname)
        if fn is None:
            errors.append(f"chybí funkce {fname}({', '.join(params)}) na nejvyšší úrovni modulu")
            continue
        a = fn.args
        if len(a.posonlyargs) + len(a.args) != 2 or a.vararg or a.kwonlyargs or a.kwarg:
            err(fn, f"funkce {fname} musí mít právě dva parametry ({', '.join(params)})")

    # --- heuristika: cykly pres pixely v render()
    if "render" in funcs and _has_nested_pixel_loops(funcs["render"]):
        err(funcs["render"], "render prochází pixely ve vnořených cyklech – to je zakázané; "
                             "použij vektorizovaný numpy (np.mgrid, np.sin, np.where, ...)")
    elif "render" in funcs and _loop_depth(funcs["render"]) >= 2:
        warnings.append("render obsahuje vnořené cykly – pravděpodobně cyklus přes pixely; "
                        "použij vektorizovaný numpy (np.mgrid, np.sin, ...)")

    return list(dict.fromkeys(errors)), warnings


# --------------------------------------------------------------------------
# 2) Podproces s limity
# --------------------------------------------------------------------------

def default_speedup():
    """Na Pi merime primo (1.0), na PC prepocitavame odhadem."""
    machine = platform.machine().lower()
    return 1.0 if machine.startswith(("arm", "aarch64")) else C.PC_SPEEDUP


NOBODY_UID = NOBODY_GID = 65534


def _limits(mem_mb, cpu_s):
    """Limity nastavene v podprocesu jeste pred spustenim Pythonu.

    Root se zahazuje az v _prepare_worker() – po nacteni skriptu a knihoven,
    protoze domovsky adresar na Pi nemusi byt citelny pro nobody.
    """
    def apply():
        os.setsid()                                           # vlastni skupina procesu
        mem = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))     # zadne zapisy do souboru
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def _sandbox_env():
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }


def _crash_message(rc, stderr, timeout):
    if rc is None:
        return f"zkušební běh překročil časový limit {timeout} s"
    if rc < 0:
        sig = signal.Signals(-rc).name
        if -rc == signal.SIGXCPU:
            return f"zkušební běh překročil limit CPU ({sig})"
        return f"zkušební běh spadl na signál {sig} (pravděpodobně limit paměti)"
    tail = "\n".join(stderr.strip().splitlines()[-5:])
    return f"zkušební běh skončil s kódem {rc}: {tail}"


def validate_source(source, filename="<animation>", speedup=None,
                    timeout=C.SANDBOX_TIMEOUT_S):
    """Kompletni validace zdrojaku. Vraci dict pro JSON."""
    speedup = default_speedup() if speedup is None else speedup
    errors, warnings = static_check(source)
    result = {"file": filename, "ok": False, "errors": errors, "warnings": warnings,
              "stats": {}, "speedup": speedup}
    if errors:
        return result

    # zdrojak posilame pres stdin, worker nemusi nic otevirat
    rc, out, err = _spawn_with_stdin(["check", filename, "--speedup", str(speedup)],
                                     source, timeout)
    dyn = _last_json(out)
    if dyn is None:
        result["errors"].append(_crash_message(rc, err, timeout))
        return result
    result["errors"].extend(dyn.get("errors", []))
    result["warnings"].extend(dyn.get("warnings", []))
    result["stats"] = dyn.get("stats", {})
    for k in ("name", "fps", "duration"):
        if k in dyn:
            result[k] = dyn[k]
    result["ok"] = not result["errors"]
    return result


def validate_file(path, speedup=None, timeout=C.SANDBOX_TIMEOUT_S):
    path = Path(path)
    return validate_source(path.read_text(encoding="utf-8"), str(path), speedup, timeout)


def _worker_cmd(args):
    return [sys.executable, "-I", str(Path(__file__).resolve()), "--worker", *args]


def _encode_source(source):
    """Zdrojak pres stdin s delkou na zacatku (stdin pak muze pokracovat dal)."""
    data = source.encode("utf-8")
    return f"{len(data)}\n".encode() + data


def _spawn_with_stdin(args, source, timeout, mem_mb=C.SANDBOX_MEM_MB):
    """Spusti tento soubor v rezimu --worker v izolovanem podprocesu.

    Zdrojak animace jde pres stdin. Vraci (returncode | None pri timeoutu,
    stdout bytes, stderr text).
    """
    cmd = _worker_cmd(args)
    try:
        p = subprocess.run(cmd, input=_encode_source(source), capture_output=True,
                           timeout=timeout, cwd="/", env=_sandbox_env(),
                           preexec_fn=_limits(mem_mb, timeout))
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b"", (e.stderr or b"").decode("utf-8", "replace")
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def popen_serve(source, filename, cpu_s, mem_mb=C.SANDBOX_MEM_MB):
    """Spusti worker v rezimu serve (pro prehravac) a posle mu zdrojak.

    Protokol: worker po init() posle b"R". Pak na kazdy pozadavek
    (8 bajtu, struct "<d" = cas t) odpovi FRAME_BYTES bajty RGB snimku.
    Pri chybe skonci, traceback je na stderr.
    """
    p = subprocess.Popen(_worker_cmd(["serve", filename]), stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/",
                         env=_sandbox_env(), preexec_fn=_limits(mem_mb, cpu_s))
    p.stdin.write(_encode_source(source))
    p.stdin.flush()
    return p


def _last_json(out):
    for line in reversed(out.decode("utf-8", "replace").strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def render_frames(source, filename="<animation>", seconds=None, timeout=C.SANDBOX_TIMEOUT_S):
    """Vyrenderuje snimky v podprocesu (pro preview). Vraci (meta, [np.ndarray])."""
    import numpy as np
    args = ["frames", filename] + (["--seconds", str(seconds)] if seconds else [])
    rc, out, err = _spawn_with_stdin(args, source, timeout)
    nl = out.find(b"\n")
    meta = json.loads(out[:nl]) if nl >= 0 else None
    if rc != 0 or meta is None:
        raise RuntimeError(_crash_message(rc, err, timeout))
    data = out[nl + 1:]
    n = meta["frames"]
    if len(data) != n * FRAME_BYTES:
        raise RuntimeError("podproces vrátil neúplná data")
    arr = np.frombuffer(data, dtype=np.uint8).reshape(n, C.HEIGHT, C.WIDTH, C.CHANNELS)
    return meta, list(arr)


# --------------------------------------------------------------------------
# 3) Worker (bezi v podprocesu, nikdy v procesu prehravace)
# --------------------------------------------------------------------------

def _prepare_worker():
    """Predimportuje povolene moduly, presmeruje print() a zakaze nove soubory.

    Vraci binarni stream pro vysledek (puvodni stdout).
    """
    import colorsys, math  # noqa: F401,E401
    import numpy  # noqa: F401
    import numpy.random, numpy.linalg, numpy.fft  # noqa: F401,E401
    import PIL.Image, PIL.ImageDraw, PIL.ImageFilter, PIL.ImageChops  # noqa: F401,E401
    import PIL.ImageOps, PIL.ImageEnhance, PIL.ImageColor, PIL.ImageFont  # noqa: F401,E401

    result_out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)                       # print() z animace jde do stderr
    sys.stdout = sys.stderr
    if os.getuid() == 0:                # pod sudo: zahodit root
        os.setgroups([])
        os.setgid(NOBODY_GID)
        os.setuid(NOBODY_UID)
    lim = result_out.fileno() + 1       # od ted zadne nove deskriptory (soubory, sokety)
    resource.setrlimit(resource.RLIMIT_NOFILE, (lim, lim))
    # zadne nove procesy ani vlakna (fork). Root limit ignoruje, proto
    # _limits() pod sudo prepina na uzivatele nobody.
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    return result_out


def _error_from_exception(e, filename, where):
    line = None
    for fr in traceback.extract_tb(e.__traceback__):
        if fr.filename == filename:
            line = fr.lineno
    loc = f" (řádek {line})" if line else ""
    return f"výjimka v {where}{loc}: {type(e).__name__}: {e}"


def _check_frame(f):
    import numpy as np
    if not isinstance(f, np.ndarray):
        return f"render musí vracet numpy.ndarray, vrátil {type(f).__name__}"
    if f.shape != C.FRAME_SHAPE:
        return f"render vrátil tvar {f.shape}, očekává se {C.FRAME_SHAPE}"
    if f.dtype != np.uint8:
        return f"render vrátil dtype {f.dtype}, očekává se uint8 (použij .astype(np.uint8))"
    return None


def _worker_check(mod, filename, speedup):
    import numpy as np
    errors, warnings, stats = [], [], {}
    out = {"errors": errors, "warnings": warnings, "stats": stats}

    for name in C.REQUIRED_CONSTANTS + tuple(C.REQUIRED_FUNCTIONS):
        if not hasattr(mod, name):
            errors.append(f"modul nemá {name}")
    if errors:
        return out
    fps, duration = int(mod.FPS), float(mod.DURATION)
    out.update(name=mod.NAME, fps=fps, duration=duration)

    try:
        state = mod.init(C.WIDTH, C.HEIGHT)
    except Exception as e:
        errors.append(_error_from_exception(e, filename, "init()"))
        return out
    if not isinstance(state, dict):
        errors.append(f"init musí vracet dict, vrátil {type(state).__name__}")
        return out

    rng = random.Random(0)
    times = [i / fps for i in range(C.TEST_FRAMES)]
    times += sorted(rng.uniform(0, duration) for _ in range(C.TEST_EXTRA_SAMPLES))
    times.append(max(0.0, duration - 1.0 / fps))

    frames, ms = [], []
    for t in times:
        try:
            t0 = time.perf_counter()
            f = mod.render(state, t)
            ms.append((time.perf_counter() - t0) * 1000)
        except Exception as e:
            errors.append(_error_from_exception(e, filename, f"render(state, t={t:.3f})"))
            return out
        problem = _check_frame(f)
        if problem:
            errors.append(f"t={t:.3f}: {problem}")
            return out
        frames.append(f.copy())

    # cistota: stejne t -> stejny snimek
    try:
        again = mod.render(state, times[0])
        if not np.array_equal(again, frames[0]):
            errors.append("render není čistá funkce: pro stejné t vrací jiný snímek "
                          "(nepoužívej náhodu bez pevného seedu ani neměň state v render)")
    except Exception as e:
        errors.append(_error_from_exception(e, filename, "render (opakované volání)"))

    stack = np.stack(frames)
    black = int((stack.reshape(len(frames), -1).max(axis=1) <= C.BLACK_MAX_VALUE).sum())
    if black == len(frames):
        errors.append("všechny snímky jsou černé")
    elif black > len(frames) // 2:
        errors.append(f"{black} z {len(frames)} snímků je celých černých")

    diff = np.abs(stack.astype(np.int16) - stack[0].astype(np.int16)).mean(axis=(1, 2, 3))
    if diff.max() < C.STATIC_MEAN_DIFF:
        errors.append("animace je statická – snímky se v čase nemění")

    mean_level = float(stack.mean())
    if mean_level > 110:
        warnings.append(f"obraz je hodně světlý (průměr {mean_level:.0f}/255) – "
                        "na LED matici je lepší tmavé pozadí")

    timed = sorted(ms[1:] or ms)          # prvni snimek = zahrivani
    mean_ms = sum(timed) / len(timed)
    p95_ms = timed[int(0.95 * (len(timed) - 1))]
    budget = C.frame_budget_ms(fps, speedup)
    stats.update(frames_tested=len(frames), mean_ms=round(mean_ms, 3),
                 p95_ms=round(p95_ms, 3), max_ms=round(timed[-1], 3),
                 budget_ms=round(budget, 3), est_pi_mean_ms=round(mean_ms * speedup, 3),
                 black_frames=black, mean_level=round(mean_level, 1))
    if mean_ms > budget:
        errors.append(f"render je pomalý: průměr {mean_ms:.2f} ms, limit {budget:.2f} ms "
                      f"(odhad na Pi {mean_ms * speedup:.1f} ms při {fps} FPS) – "
                      "zjednoduš výpočet, předpočítej v init(), vektorizuj")
    elif p95_ms > 2 * budget:
        warnings.append(f"občas pomalé snímky: p95 {p95_ms:.2f} ms (limit {budget:.2f} ms)")
    return out


def _worker_frames(mod, result_out, seconds):
    import numpy as np
    fps = int(mod.FPS)
    seconds = float(seconds or mod.DURATION)
    n = max(1, int(round(seconds * fps)))
    state = mod.init(C.WIDTH, C.HEIGHT)
    buf = bytearray()
    for i in range(n):
        f = mod.render(state, i / fps)
        problem = _check_frame(f)
        if problem:
            raise ValueError(problem)
        buf += np.ascontiguousarray(f).tobytes()
    meta = {"name": mod.NAME, "fps": fps, "duration": float(mod.DURATION), "frames": n}
    result_out.write(json.dumps(meta).encode() + b"\n")
    result_out.write(bytes(buf))
    result_out.flush()


def _worker_serve(mod, result_out):
    import struct
    import numpy as np
    state = mod.init(C.WIDTH, C.HEIGHT)
    if not isinstance(state, dict):
        raise TypeError(f"init musí vracet dict, vrátil {type(state).__name__}")
    result_out.write(b"R")
    result_out.flush()
    stdin = sys.stdin.buffer
    while True:
        req = stdin.read(8)
        if len(req) < 8:                # prehravac zavrel rouru -> konec
            return
        (t,) = struct.unpack("<d", req)
        f = mod.render(state, t)
        problem = _check_frame(f)
        if problem:
            raise ValueError(problem)
        result_out.write(np.ascontiguousarray(f).tobytes())
        result_out.flush()


def worker_main(argv):
    p = argparse.ArgumentParser(prog="validate --worker")
    p.add_argument("mode", choices=["check", "frames", "serve"])
    p.add_argument("filename")
    p.add_argument("--speedup", type=float, default=1.0)
    p.add_argument("--seconds", type=float)
    a = p.parse_args(argv)

    size = int(sys.stdin.buffer.readline())
    source = sys.stdin.buffer.read(size).decode("utf-8")
    result_out = _prepare_worker()

    if a.mode == "serve":
        _worker_serve(C.load_animation(source, a.filename), result_out)
        return 0

    if a.mode == "frames":
        mod = C.load_animation(source, a.filename)
        _worker_frames(mod, result_out, a.seconds)
        return 0

    try:
        mod = C.load_animation(source, a.filename)
    except Exception as e:
        res = {"errors": [_error_from_exception(e, a.filename, "načtení modulu")]}
    else:
        try:
            res = _worker_check(mod, a.filename, a.speedup)
        except MemoryError:
            res = {"errors": [f"překročen limit paměti {C.SANDBOX_MEM_MB} MB"]}
    result_out.write(json.dumps(res, ensure_ascii=False).encode("utf-8") + b"\n")
    result_out.flush()
    return 0


# --------------------------------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--worker"]:
        return worker_main(argv[1:])

    p = argparse.ArgumentParser(description="Validace animací pro LED matici 64×64.")
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--speedup", type=float, default=None,
                   help=f"kolikrát je tento stroj rychlejší než Pi 4 "
                        f"(výchozí: 1 na ARM, {C.PC_SPEEDUP} jinde)")
    p.add_argument("--timeout", type=int, default=C.SANDBOX_TIMEOUT_S)
    a = p.parse_args(argv)

    results = [validate_file(f, a.speedup, a.timeout) for f in a.files]
    out = results[0] if len(results) == 1 else results
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
