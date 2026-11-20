"""Kontrakt animace pro LED matici 64x64.

Jeden soubor = jedna animace:

    NAME = "plasma_ocean"   # kratky nazev, a-z 0-9 _
    DURATION = 45           # sekund
    FPS = 20                # 10-30

    def init(w, h):         # zavola se jednou, vrati stav (dict), zadne I/O
        return {...}

    def render(state, t):   # vrati np.ndarray (64, 64, 3) uint8 RGB, t v sekundach
        ...                 # cista funkce: vysledek zavisi jen na state a t

Tento modul nesmi importovat nic krome standardni knihovny (pouziva ho
validator, preview, prehravac i generator).
"""
import re
import types

WIDTH = 64
HEIGHT = 64
CHANNELS = 3
FRAME_SHAPE = (HEIGHT, WIDTH, CHANNELS)
FRAME_DTYPE = "uint8"

FPS_MIN = 10
FPS_MAX = 30
DURATION_MIN = 5       # s
DURATION_MAX = 300     # s

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

REQUIRED_CONSTANTS = ("NAME", "DURATION", "FPS")
REQUIRED_FUNCTIONS = {"init": ("w", "h"), "render": ("state", "t")}

# Povolene importy (prvni cast jmena modulu, tj. "PIL.Image" -> "PIL").
ALLOWED_IMPORTS = frozenset({"numpy", "PIL", "math", "random", "colorsys"})

# Zakazana jmena (volani i pouhy odkaz).
FORBIDDEN_NAMES = frozenset({
    "open", "exec", "eval", "compile", "__import__", "__builtins__",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "input", "breakpoint", "help", "exit", "quit", "memoryview",
    "os", "sys", "subprocess", "socket", "importlib", "builtins",
})

# Zakazane atributy: souborove I/O v numpy a PIL, zobrazovani okna.
# (Atributy tvaru __xxx__ jsou zakazane vsechny, viz validate.py.)
FORBIDDEN_ATTRS = frozenset({
    "open", "save", "show", "load", "fromfile", "tofile", "memmap",
    "loadtxt", "savetxt", "genfromtxt", "savez", "savez_compressed",
    "ctypeslib", "DataSource", "system", "popen",
})

# Rozpocet: render smi zabrat nejvys 40 % casu snimku (merime na Pi 4).
RENDER_BUDGET_FRACTION = 0.4

# Na PC je numpy vyrazne rychlejsi nez na Pi 4. Pri validaci na PC se
# rozpocet vydeli timto koeficientem (odhad, na Pi se pouzije 1.0).
PC_SPEEDUP = 4.0

# Zkusebni beh ve validatoru
TEST_FRAMES = 100          # minimalne tolik snimku za sebou od t=0
TEST_EXTRA_SAMPLES = 20    # + nahodne casy v celem rozsahu DURATION
SANDBOX_MEM_MB = 1024      # RLIMIT_AS pro podproces
SANDBOX_TIMEOUT_S = 60     # celkovy limit zkusebniho behu

# Prah pro "cerny" snimek (max hodnota kanalu) a "staticka" animace.
BLACK_MAX_VALUE = 8
STATIC_MEAN_DIFF = 0.5


def frame_budget_ms(fps, speedup=1.0):
    """Maximalni prumerny cas render() v ms pro dane FPS."""
    return 1000.0 / fps * RENDER_BUDGET_FRACTION / speedup


def load_animation(source, filename="<animation>"):
    """Vykona zdrojovy kod animace a vrati modul.

    POZOR: spousti cizi kod. Volat jen v podprocesu s limity
    (viz runner/validate.py), nikdy v procesu prehravace.
    """
    mod = types.ModuleType("animation")
    mod.__file__ = filename
    exec(compile(source, filename, "exec"), mod.__dict__)
    return mod
