import math, sys, time, os, signal, types, subprocess, select, re, termios, tty
import numpy as np
from palette import color

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
# mouse/touch reporting: ?1003 = report all motion, ?1006 = SGR extended coords
MOUSE_ON  = "\033[?1003h\033[?1006h"
MOUSE_OFF = "\033[?1003l\033[?1006l"

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

# throughput budget (bytes/sec) after every frame we sleep long enough that our
# average write rate never exceeds set value
_BUDGET_BPS = (
    600_000    if _TERM_PROGRAM == "Apple_Terminal" else
    50_000_000 if _TERM_PROGRAM in ("WezTerm", "kitty") else
    2_000_000  # iTerm2 and everything else
)

# Synchronized Update Protocol (BSU/ESU, ?2026)
# prevents tearing
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

# 16 basic ANSI foreground colours w/ RGB values (approx)
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

# round ot nearest in 16 color set
def _nearest_ansi(r, g, b):
    def distance(entry):
        esc, (ar, ag, ab) = entry
        return (r-ar)**2 + (g-ag)**2 + (b-ab)**2
    esc, rgb = min(_ANSI16, key=distance)
    return esc

def restore(sig=None, frame=None):
    try:
        if _old_termios is not None:
            termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _old_termios)
    except Exception:
        pass
    sys.stdout.write(MOUSE_OFF + SHOW + RESET + "\n")
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGINT,  restore)
signal.signal(signal.SIGTERM, restore)

# mouse/touch state
# SGR mouse reports arrive as: ESC [ < btn ; col ; row (M=press/motion, m=release)
_MOUSE_RE = re.compile(r"\033\[<(\d+);(\d+);(\d+)([Mm])")
mouse_x = -1.0     # current touch position in cell coords; -1 = nothing yet
mouse_y = -1.0
mouse_down = False
mouse_press_t = -1.0   # value of t at the moment the current press began

_stdin_fd = sys.stdin.fileno()
try:
    _old_termios = termios.tcgetattr(_stdin_fd)   # save to restore on exit
except Exception:
    _old_termios = None                            # stdin isn't a tty (e.g. piped)

def poll_mouse():
    """Drain whatever is waiting on stdin and update mouse state. Non-blocking."""
    global mouse_x, mouse_y, mouse_down, mouse_press_t
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
    except Exception:
        return
    if not ready:
        return
    try:
        data = os.read(_stdin_fd, 4096).decode("latin-1", "ignore")
    except Exception:
        return
    for m in _MOUSE_RE.finditer(data):
        btn, col, row, kind = m.groups()
        mouse_x = float(int(col) - 1)   # terminal coords are 1-based; cells are 0-based
        mouse_y = float(int(row) - 1)
        if kind == "m":                              # button released
            mouse_down = False
        else:                                        # 'M' = press or motion
            held = (int(btn) & 3) != 3               # low 2 bits == 3 means no button (hover)
            if held and not mouse_down:              # genuine rising edge → record press
                mouse_press_t = time.monotonic() - start_time
            mouse_down = held

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
    if _TERM_PROGRAM == "Apple_Terminal":
        encode = lambda r, g, b: _nearest_ansi(r, g, b)
    elif _USE_24BIT:
        encode = lambda r, g, b: f"\033[38;2;{r};{g};{b}m"
    else:
        encode = lambda r, g, b: f"\033[38;5;{_rgb_to_8bit(r,g,b)}m"
    return [encode(*color(name, i / 255.0)) for i in range(256)]

######### shader loader 
DEFAULT = """def value(x, y, t, cols, rows):
    cx = x - cols / 2
    cy = y - rows / 2
    v = 0.0
    c = v
    return (v, c)
"""

def load(path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True) #make folder if missing
        with open(path, "w") as f:
            f.write(DEFAULT) #write with default shader texxt
    ns = {"math": _math_np, "mx": -1.0, "my": -1.0, "mdown": False, "mtime": -1.0}
    with open(path) as f:
        exec(f.read(), ns)
    return ns["value"] #render() calls this

# N_COLORS = # of distint color levels, 16 for terminal, 32 for all else
N_COLORS    = 16 if _TERM_PROGRAM == "Apple_Terminal" else 32
_COLOR_STEP = 256 // N_COLORS

######### numpy arrays rebuilt only on resize / charset change
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

######### render
def render(fn, t, cols, rows):
    global _grid_shape, _X, _Y

    if (cols, rows) != _grid_shape:
        _rebuild_arrays(cols, rows)

    _n = len(CHARS) - 1

    ######### vectorised shader call 
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

    # delta-encoded output: emit color escape only on color transitions
    # Precompute full char grid with numpy (one vectorised index, no per-cell Python)
    # checks for per-cell difference, loops only on color-changes, faster render
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

######### init
# on first boot -> calls load(SHADER)
# render loop calls (V, C = fn(...)) every frame
fn       = load(SHADER)
mtime    = os.path.getmtime(SHADER)
chars_mtime = 0
pal_mtime   = 0
pal_name = "rainbow"
lut      = make_lut(pal_name)
err      = None

_refresh_lut_chars()

if _old_termios is not None:
    try:
        tty.setcbreak(_stdin_fd)
    except Exception:
        pass
sys.stdout.buffer.write((MOUSE_ON + HIDE + CLEAR).encode("utf-8"))
sys.stdout.buffer.flush()

start_time   = time.monotonic()
# max-FPS ceiling - the throughput budget (_BUDGET_BPS) will push this lower
# automatically when frames are large (big window)
FRAME_TIME   = 1.0 / 8.0 if _TERM_PROGRAM == "Apple_Terminal" else 1.0 / 30.0
POLL_EVERY   = 3 # frames to skip
frame_count  = 0
_last_elapsed  = FRAME_TIME
_last_frame_kb = 0.0

# periodically nudge tmux so any stuck resize state self-heals within REFRESH_INTERVAL seconds
REFRESH_INTERVAL = 5.0
_last_refresh    = time.monotonic()

try:
    while True:
        frame_start = time.monotonic()
        t = frame_start - start_time

        # read touches and expose them to the shader as mx / my / mdown
        poll_mouse()
        fn.__globals__["mx"] = mouse_x
        fn.__globals__["my"] = mouse_y
        fn.__globals__["mdown"] = mouse_down
        fn.__globals__["mtime"] = mouse_press_t

        if frame_count % POLL_EVERY == 0: # every 3rd frame
            # reload shader on file change
            try:
                mt = os.path.getmtime(SHADER) #current last modified time of file
                if mt != mtime: #has the file changed since last snapshot
                    mtime = mt #store new tie
                    try:
                        fn  = load(SHADER) #relead and recompile shader
                        err = None
                    except Exception as e:
                        err = str(e) #syntax error go back to old fn
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

        if _IN_TMUX and (frame_start - _last_refresh) > REFRESH_INTERVAL:
            _last_refresh = frame_start
            try:
                subprocess.run(
                    ["tmux", "refresh-client"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=0.5,
                )
            except Exception:
                pass

        try:
            cols, rows = os.get_terminal_size()
        except OSError:
            cols, rows = 80, 24
        rows -= 1

        render_start = time.monotonic()
        frame_body = render(fn, t, cols, rows)
        render_ms = (time.monotonic() - render_start) * 1000

        fps = 1.0 / _last_elapsed
        touch = f"  touch=({mouse_x:.0f},{mouse_y:.0f})" if mouse_down else ""
        status = (RED + f" ✕  {err}"[:cols].ljust(cols) + RESET) if err else \
                 (DIM + (f" ●  {pal_name}  {cols}×{rows}  {fps:.0f}fps  {_last_frame_kb:.0f}KB  render={render_ms:.1f}ms{touch}")[:cols].ljust(cols) + RESET)

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
    try:
        if _old_termios is not None:
            termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _old_termios)
    except Exception:
        pass
    sys.stdout.buffer.write((MOUSE_OFF + SHOW).encode("utf-8"))
    sys.stdout.buffer.flush()
