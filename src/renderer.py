import math, sys, time, os, signal, types
import numpy as np

# numpy drop-in
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

HIDE = "\033[?25l"
SHOW = "\033[?25h"
CLEAR = "\033[2J"
HOME  = "\033[H"

# detect terminal
_TERM_PROGRAM = os.environ.get("TERM_PROGRAM", "")
_IN_TMUX      = "TMUX" in os.environ

# fallback: tmux strips TERM_PROGRAM from env by default
if not _TERM_PROGRAM:
    if os.environ.get("ITERM_SESSION_ID"):
        _TERM_PROGRAM = "iTerm.app"
    elif os.environ.get("WEZTERM_PANE") or os.environ.get("WEZTERM_EXECUTABLE"):
        _TERM_PROGRAM = "WezTerm"

_USE_SYNC     = _TERM_PROGRAM not in ("Apple_Terminal",)

# use 24-bit color in GPU-acceelerated envs
_USE_24BIT = _TERM_PROGRAM in ("WezTerm", "kitty") and not _IN_TMUX

# hroughput budget (bytes/sec) after every frame we sleep long enough that our
# average write rate never exceeds set value
_BUDGET_BPS = (
    600_000    if _TERM_PROGRAM == "Apple_Terminal" else
    50_000_000 if _TERM_PROGRAM in ("WezTerm", "kitty") else
    2_000_000  # iTerm2 and everything else
)

# Synchronized Update Protocol (BSU/ESU, ?2026)
# Tells the terminal: buffer this frame, render it atomically — eliminates tearing.
# Problem: inside tmux, CSI sequences (\033[...) are consumed by tmux and never
# reach the outer terminal (iTerm2, WezTerm, etc.).
# Fix: wrap in DCS passthrough (\033Ptmux;\033\033[...ESC\\) so tmux forwards
# the sequence verbatim to the outer terminal
if _USE_SYNC:
    if _IN_TMUX:
        BSU = "\033Ptmux;\033\033[?2026h\033\\"
        ESU = "\033Ptmux;\033\033[?2026l\033\\"
    else:
        BSU = "\033[?2026h"
        ESU = "\033[?2026l"
else:
    BSU = ESU = ""
RED   = "\033[31m"
DIM   = "\033[2m"
RESET = "\033[0m"

# 16 basic ANSI foreground colours with their approximate RGB values.
# Used for Apple Terminal where 8-bit escapes (10-12 bytes) are replaced by
# these 5-6 byte sequences, cutting per-escape cost ~2×.
_ANSI16 = [
    ("\033[30m", (  0,   0,   0)),  # black
    ("\033[31m", (170,   0,   0)),  # dark red
    ("\033[32m", (  0, 170,   0)),  # dark green
    ("\033[33m", (170, 170,   0)),  # dark yellow
    ("\033[34m", (  0,   0, 170)),  # dark blue
    ("\033[35m", (170,   0, 170)),  # dark magenta
    ("\033[36m", (  0, 170, 170)),  # dark cyan
    ("\033[37m", (170, 170, 170)),  # light gray
    ("\033[90m", ( 85,  85,  85)),  # dark gray
    ("\033[91m", (255,  85,  85)),  # bright red
    ("\033[92m", ( 85, 255,  85)),  # bright green
    ("\033[93m", (255, 255,  85)),  # bright yellow
    ("\033[94m", ( 85,  85, 255)),  # bright blue
    ("\033[95m", (255,  85, 255)),  # bright magenta
    ("\033[96m", ( 85, 255, 255)),  # bright cyan
    ("\033[97m", (255, 255, 255)),  # white
]

def _nearest_ansi(r, g, b):
    best_esc, best_d = _ANSI16[0][0], float("inf")
    for esc, (ar, ag, ab) in _ANSI16:
        d = (r-ar)**2 + (g-ag)**2 + (b-ab)**2
        if d < best_d:
            best_d, best_esc = d, esc
    return best_esc

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

def _rgb_to_8bit(r, g, b):
    """Map 24-bit RGB to the nearest xterm-256 colour index."""
    # Near-grays route to the grayscale ramp (232-255) instead of the cube,
    # since some terminal themes (e.g. Catppuccin) repaint cube origin 16 as a non-black colour.
    if abs(r - g) < 12 and abs(g - b) < 12 and abs(r - b) < 12:
        avg = (r + g + b) // 3
        return 232 + min(23, max(0, (avg - 8) // 10))
    ri = round(r / 255.0 * 5)
    gi = round(g / 255.0 * 5)
    bi = round(b / 255.0 * 5)
    return 16 + 36 * ri + 6 * gi + bi

# build color lookup table
def make_lut(name):
    lut = []
    for i in range(256):
        n = i / 255.0
        if name == "green":
            r, g, b = 0, int(30 + n*225), int(n*40)
        elif name == "fire":
            r = min(255, int(n*3*255)); g = min(255, max(0, int((n-.33)*3*255))); b = min(255, max(0, int((n-.66)*3*255)))
        elif name == "rainbow":
            r, g, b = hsv(n * 0.85, 1.0, 1.0)
        elif name == "plasma":
            r = int(128 + 127*math.sin(n*math.pi*2)); g = int(128 + 127*math.sin(n*math.pi*2+2.094)); b = int(128 + 127*math.sin(n*math.pi*2+4.189))
        elif name == "gold":
            r = min(255, int(n*2*255)); g = int(n*180); b = int(n*20)
        elif name == "mono":
            r = g = b = int(n * 255)
        elif name == "acid":
            h = 0.25 + 0.12 * math.sin(n * math.pi * 4)
            r, g, b = hsv(h, 1.0, 0.2 + 0.8 * n)
        elif name == "acid2":
            colors = [
                (  0,   0,   0),
                (  7,  88,   0),
                (137, 255,   0),
                (200, 212, 138),
                (253, 255,   0),
            ]
            segments = len(colors) - 1
            pos = n * segments
            lo  = min(int(pos), segments - 1)
            hi  = lo + 1
            t2  = pos - lo
            r   = int(colors[lo][0] + (colors[hi][0] - colors[lo][0]) * t2)
            g   = int(colors[lo][1] + (colors[hi][1] - colors[lo][1]) * t2)
            b   = int(colors[lo][2] + (colors[hi][2] - colors[lo][2]) * t2)
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
        elif name == "toxic":
            colors = [(0,0,0),(10,40,0),(60,180,0),(180,255,0),(220,255,50)]
            segments = len(colors) - 1
            pos = n * segments; lo = min(int(pos), segments-1); hi = lo+1; t2 = pos-lo
            r = int(colors[lo][0]+(colors[hi][0]-colors[lo][0])*t2)
            g = int(colors[lo][1]+(colors[hi][1]-colors[lo][1])*t2)
            b = int(colors[lo][2]+(colors[hi][2]-colors[lo][2])*t2)
        elif name == "lava":
            colors = [(0,0,0),(120,0,0),(255,40,0),(255,160,0),(255,255,200)]
            segments = len(colors) - 1
            pos = n * segments; lo = min(int(pos), segments-1); hi = lo+1; t2 = pos-lo
            r = int(colors[lo][0]+(colors[hi][0]-colors[lo][0])*t2)
            g = int(colors[lo][1]+(colors[hi][1]-colors[lo][1])*t2)
            b = int(colors[lo][2]+(colors[hi][2]-colors[lo][2])*t2)
        elif name == "electricity":
            colors = [(0,0,0),(20,0,80),(0,60,255),(100,200,255),(255,255,255)]
            segments = len(colors) - 1
            pos = n * segments; lo = min(int(pos), segments-1); hi = lo+1; t2 = pos-lo
            r = int(colors[lo][0]+(colors[hi][0]-colors[lo][0])*t2)
            g = int(colors[lo][1]+(colors[hi][1]-colors[lo][1])*t2)
            b = int(colors[lo][2]+(colors[hi][2]-colors[lo][2])*t2)
        else:
            r, g, b = hsv(n * 0.85, 1.0, 1.0)
        if _TERM_PROGRAM == "Apple_Terminal":
            lut.append(_nearest_ansi(r, g, b))
        elif _USE_24BIT:
            lut.append(f"\033[38;2;{r};{g};{b}m")
        else:
            lut.append(f"\033[38;5;{_rgb_to_8bit(r,g,b)}m")
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

# N_COLORS must match the number of distinct colour values the lut can produce.
# Apple Terminal uses 16 ANSI colours; everything else uses 32 (8-bit or 24-bit).
N_COLORS    = 16 if _TERM_PROGRAM == "Apple_Terminal" else 32
_COLOR_STEP = 256 // N_COLORS

# ── numpy arrays rebuilt only on resize / charset change ──────────────────────
_grid_shape = (0, 0)
_X = _Y = None
_chars_arr  = None   # (n_chars,) numpy string array for fast per-cell char lookup

def _rebuild_arrays(cols, rows):
    global _grid_shape, _X, _Y
    _X, _Y = np.meshgrid(np.arange(cols, dtype=np.float64),
                          np.arange(rows,  dtype=np.float64))
    _grid_shape = (cols, rows)

def _refresh_lut_chars():
    global _chars_arr
    _chars_arr = np.array(list(CHARS))

# ── render ─────────────────────────────────────────────────────────────────────
def render(fn, t, cols, rows):
    global _grid_shape, _X, _Y

    if (cols, rows) != _grid_shape:
        _rebuild_arrays(cols, rows)

    _n = len(CHARS) - 1

    # ── vectorised shader call ────────────────────────────────────────────
    try:
        V, C = fn(_X, _Y, t, cols, rows)
        V = np.clip(np.broadcast_to(np.asarray(V, dtype=np.float64), (rows, cols)), 0.0, 1.0)
        C = np.clip(np.broadcast_to(np.asarray(C, dtype=np.float64), (rows, cols)), 0.0, 1.0)
        vi = np.minimum((V * _n + 0.5).astype(np.int32), _n)
        # Quantise to N_COLORS levels then map back into the full 256-entry lut
        ci = np.minimum((C * (N_COLORS - 1) + 0.5).astype(np.int32), N_COLORS - 1) * _COLOR_STEP
    except Exception:
        vi = np.zeros((rows, cols), dtype=np.int32)
        ci = np.zeros((rows, cols), dtype=np.int32)
        for y in range(rows):
            for x in range(cols):
                try:
                    v, c = fn(x, y, t, cols, rows)
                    vi[y, x] = int(max(0.0, min(1.0, float(v))) * _n)
                    ci[y, x] = int(max(0.0, min(1.0, float(c))) * (N_COLORS - 1)) * _COLOR_STEP
                except Exception:
                    pass

    # ── delta-encoded output: emit color escape only on color transitions ──
    # Precompute full char grid with numpy (one vectorised index, no per-cell Python).
    # Python loop runs only over color-change boundaries — far fewer iterations
    # than cells, especially with quantised colors creating multi-cell runs.
    vi_chars = _chars_arr[vi]   # (rows, cols) array of single-char strings
    rows_out = []
    for y in range(rows):
        row_ci      = ci[y]
        row_vi_chars = vi_chars[y]
        changes     = np.empty(cols, dtype=bool)
        changes[0]  = True
        changes[1:] = row_ci[1:] != row_ci[:-1]
        change_idx  = np.where(changes)[0].tolist()

        parts      = []
        n_changes  = len(change_idx)
        for k, start in enumerate(change_idx):
            end = change_idx[k + 1] if k + 1 < n_changes else cols
            parts.append(lut[row_ci[start]])
            parts.append("".join(row_vi_chars[start:end].tolist()))
        rows_out.append("".join(parts))

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

sys.stdout.buffer.write((HIDE + CLEAR).encode("utf-8"))
sys.stdout.buffer.flush()

start_time   = time.monotonic()
# max-FPS ceiling - the throughput budget (_BUDGET_BPS) will push this lower
# automatically when frames are large (big window)
FRAME_TIME   = 1.0 / 8.0 if _TERM_PROGRAM == "Apple_Terminal" else 1.0 / 30.0
POLL_EVERY   = 3
frame_count  = 0
_last_elapsed  = FRAME_TIME
_last_frame_kb = 0.0

try:
    while True:
        frame_start = time.monotonic()
        t = frame_start - start_time

        if frame_count % POLL_EVERY == 0:
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

        frame_count += 1

        try:
            cols, rows = os.get_terminal_size()
        except OSError:
            cols, rows = 80, 24
        rows -= 1

        render_start = time.monotonic()
        frame_body = render(fn, t, cols, rows)
        render_ms = (time.monotonic() - render_start) * 1000

        fps = 1.0 / _last_elapsed
        status = (RED + f" ✕  {err}"[:cols].ljust(cols) + RESET) if err else \
                 (DIM + f" ●  {pal_name}  {cols}×{rows}  {fps:.0f}fps  {_last_frame_kb:.0f}KB  render={render_ms:.1f}ms".ljust(cols) + RESET)

        try:
            data = (BSU + HIDE + frame_body + f"\033[{rows+1};1H" + status + "\033[1;1H" + ESU).encode("utf-8")
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        except OSError:
            pass

        elapsed        = time.monotonic() - frame_start
        _last_elapsed  = elapsed
        _last_frame_kb = len(data) / 1024
        # sleep whichever is longer: FPS ceiling or throughput budget
        # FPS scales down automatically for large windows/slow terminals
        budget_time = len(data) / _BUDGET_BPS
        sleep_time  = max(FRAME_TIME, budget_time) - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
finally:
    sys.stdout.buffer.write(SHOW.encode("utf-8"))
    sys.stdout.buffer.flush()
