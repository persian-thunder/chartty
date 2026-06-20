import os, re, readline, subprocess
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from palette import NAMES as PALETTES

_SRC       = os.path.dirname(os.path.abspath(__file__))
_CONFIG    = os.path.join(_SRC, "..", "config")
SHADER     = os.path.join(_CONFIG, "shader.py")
CHARS_FILE = os.path.join(_CONFIG, "chars.txt")
PAL_FILE   = os.path.join(_CONFIG, "palette.txt")

### ascii charsets, add more here or type your own
PRESETS = {
    "default": " ·:│▒█",
    "ascii":   " .:-=+*#%@",
    "block":   " ░▒▓█",
    "binary":  " 01",
    "slash":   " /|\\-",
    "dot":     " .:·•●",
    "zen":     " ⠁⠃⠇⠇⣇⣧⣷⣿",
    "kawaii":  " ₊˚⊙♥✧✦",
    "dense":   " .'`^\",;:Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "shade":   " ·∙○◎●",
    "cross":   " ╌╍═╪╬",
    "circuit": " ·─│┼╬",
    "noise":   " .,;!?*#@",
    "wave":    " ~≈≋",
    "heart":   " ♡♥",
    "star":    " ·✦✧★",
    "braille": " ⠂⠆⠖⠶⠷⠿",
    "box":     " ▖▗▘▙▚▛▜▝▞▟█",
    "pixel":   " ▏▎▍▌▋▊▉█",
    "tri":     " ▴▵△▲",
    "matrix":  " ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵ",
    "hex":     " 0123456789ABCDEF",
    "swoosh":  " ·∕╱⟩»❯➤✓✔",
    "photo":   " .,:;i1tfLCG08@",
}

###repl color code
DIM    = "\033[2m"
GREEN  = "\033[32m"
RED    = "\033[31m"
RESET  = "\033[0m"
ORANGE = "\033[38;2;255;140;0m"
CYAN   = "\033[38;2;0;200;255m"
LIME   = "\033[38;2;50;255;100m"
PINK   = "\033[38;2;255;80;180m"
PURPLE = "\033[38;2;180;100;255m"
GOLD   = "\033[38;2;255;220;50m"

_VAR_COLORS = {
    'cols': PURPLE, 'rows': PURPLE,
    'cx': CYAN, 'cy': CYAN, 'x': CYAN, 'y': CYAN,
    't': LIME, 'v': ORANGE, 'c': PINK,
}
_HL_PAT = re.compile(r'\b(?:cols|rows|cx|cy|x|y|t|v|c)\b|math\.(?:atan2|atan|asin|acos|sinh|cosh|tanh|sin|cos|tan)')

def _highlight(line):
    def _sub(m):
        w = m.group()
        if '.' in w:
            prefix, func = w.split('.', 1)
            return prefix + '.' + GOLD + func + RESET
        return _VAR_COLORS.get(w, w) + w + RESET
    return _HL_PAT.sub(_sub, line)

BOILERPLATE_TOP = """def value(x, y, t, cols, rows):
    cx = x - cols / 2
    cy = y - rows / 2
    v = 0.0
"""

BOILERPLATE_BOT = """    c = v
    return (v, c)
"""

###startup banner
CHARTTY_BANNER = [
    "₊ ⊙ ♡ ✧ ✦ ♥ ✦ ✧ ♡ ⊙ ₊ ⊙ ♡ ✧ ✦ ♥ ✦ ✧ ♡ ⊙ ₊ ⊙ ♡ ✧ ✦ ♥ ✦ ✧ ♡ ⊙",
    " ██████╗██╗  ██╗ █████╗ ██████╗ ████████╗████████╗██╗   ██╗",
    "██╔════╝██║  ██║██╔══██╗██╔══██╗╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝",
    "██║     ███████║███████║██████╔╝   ██║      ██║    ╚████╔╝ ",
    "██║     ██╔══██║██╔══██║██╔══██╗   ██║      ██║     ╚██╔╝  ",
    "╚██████╗██║  ██║██║  ██║██║  ██║   ██║      ██║      ██║   ",
    " ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═╝      ╚═╝   ",
    "⊙ ₊ ♡ ✧ ✦ ♥ ✦ ✧ ♡ ⊙ ₊ ⊙ ♡ ✧ ✦ ♥ ✦ ✧ ♡ ⊙ ₊ ⊙ ♡ ✧ ✦ ♥ ✦ ✧ ♡ ⊙",
]

def print_banner():
    stops = [(255, 130, 200), (200, 150, 255), (130, 220, 255)]  # pink → lavender → baby blue
    n = len(CHARTTY_BANNER)
    for i, line in enumerate(CHARTTY_BANNER):
        t = i / (n - 1)
        seg = t * (len(stops) - 1)
        idx = min(int(seg), len(stops) - 2)
        local_t = seg - idx
        c0, c1 = stops[idx], stops[idx + 1]
        r = int(c0[0] + (c1[0] - c0[0]) * local_t)
        g = int(c0[1] + (c1[1] - c0[1]) * local_t)
        b = int(c0[2] + (c1[2] - c0[2]) * local_t)
        print(f"  \033[38;2;{r};{g};{b}m{line}\033[0m")

###examples
EXAMPLES = [
    ("moiré wormhole",   ["r = math.sqrt((cx * 0.55) * (cx * 0.55) + cy * cy) + 0.001",
                          "a = math.atan2(cy, cx)",
                          "v = math.sin(r / 4.0 - t * 5.0) * math.sin(a * 7.0 + t * 1.5)",
                          "v += 0.5 * math.sin(r / 2.0 - t * 3.0) * math.sin(a * 13.0 - t * 0.7)",
                          "v = v * 0.5 + 0.5",
                          "c = math.sin(a * 3.0 + r / 4.0 - t * 2.0) * 0.5 + 0.5"]),
    ("acid grid",        ["v = math.sin(x / 3.0 + math.sin(y / 4.0 + t))",
                          "v += math.sin(y / 3.0 + math.sin(x / 4.0 - t))"]),
    ("breathing spiral", ["v = math.sin(math.atan2(cy, cx) * 5.0 - math.sqrt(cx*cx + cy*cy) / 3.0 + t * 2.0)"]),
    ("zoom tunnel",      ["r = math.sqrt(cx*cx + cy*cy) + 0.001",
                          "v = math.sin(10.0 / r - t * 4.0) * math.sin(math.atan2(cy, cx) * 3.0)"]),
    ("glitch ripple",    ["v = math.sin(x / 4.0 + math.sin(t + y / 20.0) * 10.0)",
                          "v += math.sin(y / 2.0 - t * 2.0) * 0.5",
                          "v = math.sin(v * math.pi * 2.0)"]),
    ("groove",           ["v = math.sin(x / 3.0 + math.sin(y / 4.0 + t))",
                          "v += math.sin(y / 3.0 + math.sin(x / 4.0 - t))",
                          "v = math.sin(x / 3.0 + math.sin(y /4.0 + t))",
                          "v += math.sin(y / 3.0 + math.sin(x / 4.0 - t))",
                          "v += math.sin(y / 3.0 + math.sin(x / 4.0 - t))"]),
]

###preset examples
SHORTCUTS = {"wormhole": 0, "acid": 1, "spiral": 2, "tunnel": 3, "ripple": 4, "groove": 5}

###default animation = acid grid grid
lines = ["v = math.sin(x / 3.0 + math.sin(y / 4.0 + t))",
         "v += math.sin(y / 3.0 + math.sin(x / 4.0 - t))"]

###default layout = horizontal
_layout = "horizontal"

def toggle_layout():
    global _layout
    session = os.environ.get("TMUX", "")
    if not session:
        print(f"{RED}  not inside tmux{RESET}")
        return
    if _layout == "horizontal":
        subprocess.call(["tmux", "select-layout", "even-vertical"])
        _layout = "vertical"
        print(f"{DIM}  layout → vertical (renderer top, editor bottom){RESET}")
    else:
        subprocess.call(["tmux", "select-layout", "even-horizontal"])
        # even-horizontal resets to 50/50; re-pin this pane so CHARTTY never wraps
        pane = os.environ.get("TMUX_PANE", "")
        cols = os.environ.get("CHARTTY_REPL_COLS", "72")
        if pane:
            subprocess.call(["tmux", "resize-pane", "-t", pane, "-x", cols])
        _layout = "horizontal"
        print(f"{DIM}  layout → horizontal (renderer left, editor right){RESET}")

_editor_hidden = False

def toggle_editor():
    global _editor_hidden
    if not os.environ.get("TMUX", ""):
        print(f"{RED} not inside tmux{RESET}")
        return
    pane = os.environ.get("TMUX_PANE", "")
    full = os.environ.get("CHARTTY_REPL_COLS", "72") #width to restore to
    if _editor_hidden:
        subprocess.call(["tmux", "resize-pane", "-t", pane, "-x", full])
        _editor_hidden = False
        print(f"{DIM} editor -> shown{RESET}")
    else:
        subprocess.call(["tmux", "resize-pane", "-t", pane, "-x", "8"])
        _editor_hidden = True
        print(f"{DIM} editor -> hidden{RESET}")

def write_shader():
    body = "".join("    " + l + "\n" for l in lines)
    with open(SHADER, "w") as f:
        f.write(BOILERPLATE_TOP + body + BOILERPLATE_BOT)

def try_compile(src=None):
    import types
    if src is None:
        with open(SHADER) as f:
            src = f.read()
    try:
        import numpy as np
        _math_np = types.SimpleNamespace(
            sin=np.sin, cos=np.cos, tan=np.tan,
            asin=np.arcsin, acos=np.arccos, atan=np.arctan, atan2=np.arctan2,
            sqrt=np.sqrt, exp=np.exp, log=np.log, log2=np.log2, log10=np.log10,
            pow=np.power, fabs=np.fabs, abs=np.fabs,
            floor=np.floor, ceil=np.ceil,
            hypot=np.hypot, sinh=np.sinh, cosh=np.cosh, tanh=np.tanh,
            fmod=np.fmod, pi=np.pi, e=np.e, inf=np.inf,
        )
        ns = {"math": _math_np}
        exec(compile(src, SHADER, "exec"), ns)
        fn = ns["value"]
        X, Y = np.meshgrid(np.arange(80, dtype=float), np.arange(24, dtype=float))
        with np.errstate(divide="ignore", invalid="ignore"):
            fn(X, Y, 0.0, 80, 24)
    except ImportError:
        import math as _math
        ns = {"math": _math}
        try:
            exec(compile(src, SHADER, "exec"), ns)
            ns["value"](0, 0, 0.0, 80, 24)
        except Exception as e:
            return False, str(e)[:100]
    except Exception as e:
        return False, str(e)[:100]
    return True, ""

def show():
    print(DIM + "─" * 36 + RESET)
    for i, l in enumerate(lines):
        print(f"{ORANGE}{i:2}{RESET}  {_highlight(l)}")
    print(DIM + "─" * 36 + RESET)

def set_chars(s):
    with open(CHARS_FILE, "w") as f:
        f.write(s)
    print(f"{DIM}  chars → {s}{RESET}")

def set_palette(name):
    with open(PAL_FILE, "w") as f:
        f.write(name)
    print(f"{DIM}  palette → {name}{RESET}")


def show_examples():
    print(f"\n{DIM}── examples ───────────────────────────────────{RESET}")
    for name, ex_lines in EXAMPLES:
        print(f"\n  {name}")
        for l in ex_lines:
            print(f"{DIM}    > {RESET}{_highlight(l)}")


### ### COMMAND DEFINITIONS ### ###
### show current shader code
def cmd_list(arg):
    show()

### show examples
def cmd_examples(arg):
    show_examples()

### open editor
def cmd_edit(arg):
    global lines
    original = list(lines)
    state = {"err": ""}      # holds the live compile error, if any

    kb = KeyBindings()

    @kb.add("c-s")
    def _(event):
        event.app.exit(result="save")

    @kb.add("c-c")
    def _(event):
        event.app.exit(result="cancel")

    ### live edit
    def on_change(buf):
        global lines
        candidate = [l for l in buf.text.split("\n") if l.strip()]
        if not candidate:
            return
        src = BOILERPLATE_TOP + "".join("    " + l + "\n" for l in candidate) + BOILERPLATE_BOT
        ok, err = try_compile(src)        # in-memory; nothing written yet
        if ok:
            lines = candidate
            write_shader()                # only valid source ever hits disk
            state["err"] = ""
        else:
            state["err"] = err            # keep last-good live; show WHY it's frozen

    def toolbar():
        return f" ✕ {state['err']}" if state["err"] else " ✓ live"

    session = PromptSession(
        multiline=True,
        key_bindings=kb,
        prompt_continuation=lambda w, ln, soft: "  ",
        bottom_toolbar=toolbar,
    )
    session.default_buffer.on_text_changed += on_change
    print(f"{DIM}  -- edit mode --{RESET}")
    print()
    print(f"{DIM}  ^S save  ^C cancel  enter = newline  type to live-edit{RESET}")

    result = session.prompt("  ", default="\n".join(lines))

    if result == "cancel":
        lines = original
        write_shader()
        print(f"{DIM}  reverted.{RESET}")
    else:
        print(f"{DIM}  saved.{RESET}")

### toggle layout
def cmd_layout(arg):
    toggle_layout()

def cmd_editor(arg):
    toggle_editor()

### clear canvas
def cmd_clear(arg):
    global lines
    lines = ["v = 0.0"]
    write_shader()
    show()

### undo most recent change
def cmd_undo(arg):
    if len(lines) > 1:
        lines.pop()
    write_shader()
    show()

###set palette
def cmd_palette(arg):
    if arg in PALETTES:
        set_palette(arg)
    elif arg == "":
        print(f"{DIM}  palettes:{RESET}")
        for p in PALETTES:
            print(f"{DIM}    palette {p}{RESET}")
    else:
        print(f"{RED}  unknown palette — try: {' '.join(PALETTES)}{RESET}")

###set charset
def cmd_chars(arg):
    if arg in PRESETS:
        set_chars(PRESETS[arg])
    elif len(arg) >= 2:
        set_chars(arg)
    else:
        print(f"{DIM}  presets: {' '.join(PRESETS)}{RESET}")

###all commands
COMMANDS = {
    "list": cmd_list, "clear": cmd_clear, "undo": cmd_undo, "examples": cmd_examples, "edit": cmd_edit, "layout": cmd_layout, "palette": cmd_palette, "chars": cmd_chars, "editor": cmd_editor,
}

###header, startup
write_shader()

#print()
print_banner()
print()
#print(f" {ORANGE}˖⁺ ·₊˚♥˚₊· ⁺˖ CHARTTY LIVE-CODE ASCII RENDERER ˖⁺ ·₊˚♥˚₊· ⁺˖{RESET}  ")
#print()
print("  Shader variables")
print(f"  {DIM}(x,y)   pixel position   (cx,cy) = centered{RESET}")
print(f"  {DIM}(t)     time             (cols,rows) terminal size{RESET}")
print(f"  {DIM}(v)     brightness 0..1  (c) colour 0..1 (defaults to v){RESET}")
print()
print("  Type Python expressions  (math.sin, math.cos, etc.)")
print()
print("  Commands")
print(f"  {DIM}<enter>  = add line          undo    = remove last line{RESET}")
print(f"  {DIM}list     = show code         clear   = reset{RESET}")
print(f"  {DIM}palette  = show/set palette  chars   = show/set charset{RESET}")
print(f"  {DIM}examples = show presets      edit    = live-edit (^S save, ^C cancel){RESET}")
print(f"  {DIM}layout   = toggle horiz/vert split{RESET}")
print()
show()

###### REPL LOOP ######
while True:
    try:
        raw = input(f"\n{GREEN}>{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not raw:
        continue

    name, _, arg = raw.partition(" ")

    if name in COMMANDS:
        COMMANDS[name](arg)
        
    elif name == "del":
        try:
            idx = int(arg)
            if idx == 0 and len(lines) == 1:
                print(f"{RED}  can't delete the only line{RESET}")
            elif 0 <= idx < len(lines):
                removed = lines.pop(idx)
                write_shader()
                ok, err = try_compile()
                if ok:
                    print(f"{DIM}  removed: {removed}{RESET}")
                    show()
                else:
                    lines.insert(idx, removed)
                    write_shader()
                    try_compile()
                    print(f"{RED}  error after del: {err}{RESET}")
            else:
                print(f"{RED}  no line {idx}{RESET}")
        except ValueError:
            print(f"{RED}  usage: del <number>{RESET}")

    elif raw in SHORTCUTS:
        ex_name, ex_lines = EXAMPLES[SHORTCUTS[raw]]
        lines = list(ex_lines)
        write_shader()
        ok, err = try_compile()
        if ok:
            show()
            print(f"{DIM}  loaded: {ex_name}{RESET}")
        else:
            print(f"{RED}  {err}{RESET}")
            
    else:
        lines.append(raw)
        write_shader()
        ok, err = try_compile()
        if ok:
            print(f"{DIM}  ✓{RESET}")
            show()
        else:
            lines.pop()
            write_shader()
            print(f"{RED}  error: {err}{RESET}")
