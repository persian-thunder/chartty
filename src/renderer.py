import math, sys, time, os, signal, types
import numpy as np

# numpy drop-in for math — lets shader run on the full pixel grid at once
_math_np = types.SimpleNamespace(
    sin=np.sin,   cos=np.cos,   tan=np.tan,
    asin=np.arcsin, acos=np.arccos, atan=np.arctan, atan2=np.arctan2,
    sqrt=np.sqrt, exp=np.exp,
    log=np.log,   log2=np.log2, log10=np.log10,
    pow=np.power, fabs=np.fabs, abs=np.fabs,
    floor=np.floor, ceil=np.ceil,
    hypot=np.hypot, sinh=np.sinh, cosh=np.cosh, tanh=np.tanh,
    fmod=np.fmod,
    pi=np.pi, e=np.e, inf=np.inf,
)

_SRC       = os.path.dirname(os.path.abspath(__file__))
_CONFIG    = os.path.join(_SRC, "..", "config")
SHADER     = os.path.join(_CONFIG, "shader.py")
CHARS_FILE = os.path.join(_CONFIG, "chars.txt")
PAL_FILE   = os.path.join(_CONFIG, "palette.txt")
CHARS      = " ·:│▒█"

HIDE  = "\033[?25l"
SHOW  = "\033[?25h"
CLEAR = "\033[2J"
HOME  = "\033[H"
RED   = "\033[31m"
DIM   = "\033[2m"
RESET = "\033[0m"

def restore(sig=None, frame=None):
    sys.stdout.write(SHOW + RESET + "\n")
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGINT,  restore)
signal.signal(signal.SIGTERM, restore)

# ── palettes ───────────────────────────────────────────────────────────────────
def hsv(h, s, v):
    h = h % 1.0; i = int(h * 6); f = h * 6 - i
    p, q, t2 = v*(1-s), v*(1-f*s), v*(1-(1-f)*s)
    r, g, b = [(v,t2,p),(q,v,p),(p,v,t2),(p,q,v),(t2,p,v),(v,p,q)][i % 6]
    return int(r*255), int(g*255), int(b*255)

def make_lut(name):
    lut = []
    for i in range(256):
        n = i / 255.0
        if name == "green":
            r, g, b = 0, int(30 + n*225), int(n*40)
        elif name == "fire":
            r = min(255, int(n*3*255)); g = min(255, max(0, int((n-.33)*3*255))); b = min(255, max(0, int((n-.66)*3*255)))
        elif name == "ice":
            r = int(n*80); g = int(180 + n*75); b = 255
        elif name == "rainbow":
            r, g, b = hsv(n * 0.85, 1.0, 1.0)
        elif name == "plasma":
            r = int(128 + 127*math.sin(n*math.pi*2)); g = int(128 + 127*math.sin(n*math.pi*2+2.094)); b = int(128 + 127*math.sin(n*math.pi*2+4.189))
        elif name == "gold":
            r = min(255, int(n*2*255)); g = int(n*180); b = int(n*20)
        elif name == "rose":
            r, g, b = hsv(0.9 + n*0.15, 0.8, n)
        elif name == "mono":
            r = g = b = int(n * 255)
        elif name == "fiesta":
            colors = [
                (255, 190,  11),  # amber gold
                (251,  86,   7),  # blaze orange
                (255,   0, 110),  # neon pink
                (131,  56, 236),  # blue violet
                ( 58, 134, 255),  # azure blue
            ]
            segments = len(colors) - 1
            pos = n * segments
            lo  = min(int(pos), segments - 1)
            hi  = lo + 1
            t2  = pos - lo
            r   = int(colors[lo][0] + (colors[hi][0] - colors[lo][0]) * t2)
            g   = int(colors[lo][1] + (colors[hi][1] - colors[lo][1]) * t2)
            b   = int(colors[lo][2] + (colors[hi][2] - colors[lo][2]) * t2)
        else:
            r, g, b = hsv(n * 0.85, 1.0, 1.0)
        lut.append(f"\033[38;2;{r};{g};{b}m")
    return lut

# ── shader loader ──────────────────────────────────────────────────────────────
DEFAULT = """def value(x, y, t, cols, rows):
    cx = x - cols / 2
    cy = y - rows / 2
    v = 0.0
    c = v
    return (v, c)
"""

def load(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(DEFAULT)
    ns = {"math": _math_np}
    with open(path) as f:
        exec(compile(f.read(), path, "exec"), ns)
    return ns["value"]

# ── numpy arrays rebuilt only on resize / palette / charset change ─────────────
_grid_shape = (0, 0)
_X = _Y = None
_cell_lut  = None   # shape (n_chars, 256): precomputed color_code+char strings

def _rebuild_arrays(cols, rows):
    global _grid_shape, _X, _Y
    _X, _Y = np.meshgrid(np.arange(cols, dtype=np.float64),
                          np.arange(rows,  dtype=np.float64))
    _grid_shape = (cols, rows)

def _refresh_lut_chars():
    global _cell_lut
    lut_np   = np.array(lut)                   # (256,)
    chars_np = np.array(list(CHARS))           # (n_chars,)
    # cell_lut[vi, ci] = lut[ci] + CHARS[vi]  — one lookup per cell
    _cell_lut = np.char.add(lut_np[np.newaxis, :],   # (1,    256)
                             chars_np[:, np.newaxis])  # (n_chars, 1)

# ── render ─────────────────────────────────────────────────────────────────────
def render(fn, t, cols, rows):
    global _grid_shape, _X, _Y

    if (cols, rows) != _grid_shape:
        _rebuild_arrays(cols, rows)

    _n = len(CHARS) - 1

    # ── one vectorised shader call for the entire pixel grid ──────────────
    try:
        V, C = fn(_X, _Y, t, cols, rows)
        V = np.broadcast_to(np.clip(np.asarray(V, dtype=np.float64), 0.0, 1.0), (rows, cols))
        C = np.broadcast_to(np.clip(np.asarray(C, dtype=np.float64), 0.0, 1.0), (rows, cols))
        vi = np.minimum((V * _n).astype(np.int32), _n)
        ci = (C * 255).astype(np.int32)
    except Exception:
        # scalar fallback for non-vectorisable shaders
        vi = np.zeros((rows, cols), dtype=np.int32)
        ci = np.zeros((rows, cols), dtype=np.int32)
        for y in range(rows):
            for x in range(cols):
                try:
                    v, c = fn(x, y, t, cols, rows)
                    vi[y, x] = int(max(0.0, min(1.0, float(v))) * _n)
                    ci[y, x] = int(max(0.0, min(1.0, float(c))) * 255)
                except Exception:
                    pass

    # ── build output — single 2-D lookup + join, no per-pixel Python loop ──
    # cell_lut[vi[y], ci[y]] selects the precomputed color+char string per cell
    rows_out = []
    for y in range(rows):
        rows_out.append("".join(_cell_lut[vi[y], ci[y]].tolist()))

    return HOME + (RESET + "\n").join(rows_out) + RESET

# ── init ───────────────────────────────────────────────────────────────────────
fn       = load(SHADER)
mtime    = os.path.getmtime(SHADER)
chars_mtime = 0
pal_mtime   = 0
pal_name = "rainbow"
lut      = make_lut(pal_name)
err      = None

_refresh_lut_chars()

sys.stdout.write(HIDE + CLEAR)
sys.stdout.flush()

start_time = time.monotonic()
FRAME_TIME = 1.0 / 60.0   # 60 fps target

while True:
    frame_start = time.monotonic()
    t = frame_start - start_time

    # reload shader on file change
    try:
        mt = os.path.getmtime(SHADER)
        if mt != mtime:
            mtime = mt
            try:
                fn  = load(SHADER)
                err = None
            except Exception as e:
                err = str(e)
    except Exception:
        pass

    # reload charset
    try:
        if os.path.exists(CHARS_FILE):
            ct = os.path.getmtime(CHARS_FILE)
            if ct != chars_mtime:
                chars_mtime = ct
                with open(CHARS_FILE) as f:
                    new = f.read().strip()
                if len(new) >= 2:
                    CHARS = new
                    _refresh_lut_chars()
    except Exception:
        pass

    # reload palette
    try:
        if os.path.exists(PAL_FILE):
            pt = os.path.getmtime(PAL_FILE)
            if pt != pal_mtime:
                pal_mtime = pt
                with open(PAL_FILE) as f:
                    new_pal = f.read().strip()
                lut      = make_lut(new_pal)
                pal_name = new_pal
                _refresh_lut_chars()
    except Exception:
        pass

    try:
        cols, rows = os.get_terminal_size()
    except OSError:
        cols, rows = 80, 24
    rows -= 1

    frame_body = render(fn, t, cols, rows)

    status = (RED + f" ✕  {err}"[:cols].ljust(cols) + RESET) if err else \
             (DIM + f" ●  {pal_name}  {cols}×{rows}  t={t:.1f}".ljust(cols) + RESET)

    sys.stdout.buffer.write(
        (frame_body + f"\033[{rows+1};1H" + status).encode("utf-8")
    )
    sys.stdout.buffer.flush()

    # Precise frame pacing: sleep most of the budget, busy-wait the last 2ms.
    # time.sleep() on macOS overshoots by ~4ms; busy-wait eliminates that jitter.
    target  = frame_start + FRAME_TIME
    slack   = target - time.monotonic() - 0.002
    if slack > 0:
        time.sleep(slack)
    while time.monotonic() < target:
        pass
