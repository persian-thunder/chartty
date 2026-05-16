import os, re, readline, subprocess, tempfile
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

###acid grid default
lines = ["v = math.sin(x / 3.0 + math.sin(y / 4.0 + t))",
         "v += math.sin(y / 3.0 + math.sin(x / 4.0 - t))"]

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
        _layout = "horizontal"
        print(f"{DIM}  layout → horizontal (renderer left, editor right){RESET}")

def write_shader():
    body = "".join("    " + l + "\n" for l in lines)
    with open(SHADER, "w") as f:
        f.write(BOILERPLATE_TOP + body + BOILERPLATE_BOT)

def try_compile():
    import types
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
        with open(SHADER) as f:
            exec(compile(f.read(), SHADER, "exec"), ns)
        fn = ns["value"]
        X, Y = np.meshgrid(np.arange(80, dtype=float), np.arange(24, dtype=float))
        fn(X, Y, 0.0, 80, 24)
    except ImportError:
        import math as _math
        ns = {"math": _math}
        try:
            with open(SHADER) as f:
                exec(compile(f.read(), SHADER, "exec"), ns)
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

def open_editor():
    global lines
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("\n".join(lines))
        tmp = f.name
    editor = os.environ.get("EDITOR", "nano")
    subprocess.call([editor, tmp])
    with open(tmp) as f:
        raw = f.read()
    os.unlink(tmp)
    new_lines = [l.rstrip() for l in raw.splitlines()
                 if l.strip() and not l.strip().startswith("#")]
    if new_lines:
        old_lines = list(lines)
        lines = new_lines
        write_shader()
        ok, err = try_compile()
        if ok:
            show()
        else:
            lines = old_lines
            write_shader()
            try_compile()
            print(f"{RED}  error: {err}{RESET}")
    else:
        print(f"{RED}  empty — keeping previous{RESET}")

def show_examples():
    print(f"\n{DIM}── examples ───────────────────────────────────{RESET}")
    for name, ex_lines in EXAMPLES:
        print(f"\n  {name}")
        for l in ex_lines:
            print(f"{DIM}    > {RESET}{_highlight(l)}")

### show current shader code
def cmd_list(arg):
    show()

### show examples
def cmd_examples(arg):
    show_examples()

### open editor
def cmd_edit(arg):
    open_editor()

### toggle layout
def cmd_layout(arg):
    toggle_layout()

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

###header, startup
write_shader()

print()
print(f" {ORANGE}˖⁺ ·₊˚♥˚₊· ⁺˖ CHARTTY LIVE-CODE ASCII RENDERER ˖⁺ ·₊˚♥˚₊· ⁺˖{RESET}  ")
print()
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
print(f"  {DIM}examples = show presets      edit    = open in $EDITOR{RESET}")
print(f"  {DIM}layout   = toggle horiz/vert split{RESET}")
print()
show()

####### REPL LOOP ######
while True:
    try:
        raw = input(f"\n{GREEN}>{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not raw:
        continue
    elif raw == "clear":
        lines = ["v = 0.0"]
        write_shader()
        show()
    elif raw == "undo":
        if len(lines) > 1:
            lines.pop()
        write_shader()
        show()
    elif raw == "list":
        show()
    elif raw == "examples":
        show_examples()
    elif raw == "layout":
        toggle_layout()
    elif raw == "edit":
        open_editor()
    elif raw.startswith("palette"):
        arg = raw[7:].strip()
    elif raw.startswith("chars"):
        arg = raw[5:].strip()
        if arg in PRESETS:
            set_chars(PRESETS[arg])
        elif len(arg) >= 2:
            set_chars(arg)
        else:
            print(f"{DIM}  presets: {' '.join(PRESETS)}{RESET}")
    elif raw.startswith("del "):
        try:
            idx = int(raw[4:].strip())
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
        name, ex_lines = EXAMPLES[SHORTCUTS[raw]]
        lines = list(ex_lines)
        write_shader()
        ok, err = try_compile()
        if ok:
            show()
            print(f"{DIM}  loaded: {name}{RESET}")
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
