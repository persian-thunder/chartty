import os, re, readline, subprocess, tempfile

DIR         = os.path.dirname(os.path.abspath(__file__))
SHADER_BODY = os.path.join(DIR, "shader_body.c")
COMPILE     = os.path.join(DIR, "compile_shader.sh")
CHARS_FILE  = os.path.join(DIR, "chars.txt")
PAL_FILE    = os.path.join(DIR, "palette.txt")

PALETTES = ["rainbow", "fire", "plasma", "ice", "green", "gold", "rose", "neon", "mono"]

PRESETS = {
    "default": " \u00b7:\u2502\u2592\u2588",
    "ascii":   " .:-=+*#%@",
    "block":   " \u2591\u2592\u2593\u2588",
    "binary":  " 01",
    "slash":   " /|\\-",
    "dot":     " .:\u00b7\u2022\u25cf",
    "zen":     " \u2801\u2803\u2807\u2847\u28c7\u28e7\u28f7\u28ff",
    "kawaii":  " \u208a\u02da\u2299\u2665\u2727\u2726",
    "dense":   " .'`^\",;:Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "shade":   " \u00b7\u2219\u25cb\u25ce\u25cf",
    "cross":   " \u254c\u254d\u2550\u256a\u256c",
    "circuit": " \u00b7\u2500\u2502\u253c\u256c",
    "noise":   " .,;!?*#@",
    "wave":    " ~\u2248\u224b",
    "heart":   " \u2661\u2665",
    "star":    " \u00b7\u2726\u2727\u2605",
    "braille": " \u2802\u2806\u2816\u2836\u2837\u283f",
    "math":    " \u2218\u2219\u25e6\u25cb\u25cf",
    "box":     " \u2596\u2597\u2598\u2599\u259a\u259b\u259c\u259d\u259e\u259f\u2588",
    "pixel":   " \u258f\u258e\u258d\u258c\u258b\u258a\u2589\u2588",
    "tri":     " \u25b4\u25b5\u25b3\u25b2",
    "diamond": " \u00b7\u25c7\u25c6",
    "fire2":   " .,*#@\u2591\u2592\u2593\u2588",
    "matrix":  " \uff66\uff67\uff68\uff69\uff6a\uff6b\uff6c\uff6d\uff6e\uff6f\uff70\uff71\uff72\uff73\uff74\uff75",
    "hex":     " 0123456789ABCDEF",
    "morse":   " .-",
    "thick":   " \u2592\u2588",
}

DIM   = "\033[2m"
GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"

# ── Python → C auto-translation ───────────────────────────────────────────────
_MATH_FNS = [
    "sin","cos","tan","asin","acos","atan","atan2",
    "sqrt","exp","log","log2","log10","pow",
    "fabs","ceil","floor","hypot","sinh","cosh","tanh","fmod",
]

def py_to_c(line):
    """Best-effort translate Python math expression to C.

    Handles:
      math.XXX(  →  XXX(
      math.pi    →  M_PI
      math.e     →  M_E
      abs(       →  fabs(
      trailing semicolon added if missing
    """
    for fn in _MATH_FNS:
        line = line.replace(f"math.{fn}(", f"{fn}(")
    line = line.replace("math.pi",  "M_PI")
    line = line.replace("math.e",   "M_E")
    line = line.replace("math.inf", "INFINITY")
    line = re.sub(r"\babs\(", "fabs(", line)
    stripped = line.rstrip()
    if stripped and not stripped.endswith((";", "{", "}", "//", "*/")):
        line = stripped + ";"
    return line

# ── shader file I/O ───────────────────────────────────────────────────────────
lines = ["v = sin(cos(t + cx) * sin(cx + t));"]   # stored as C

def write_shader():
    with open(SHADER_BODY, "w") as f:
        for l in lines:
            f.write("    " + l + "\n")

def try_compile():
    """Returns (ok: bool, short_error: str)."""
    r = subprocess.run(
        ["bash", COMPILE],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        return True, ""
    # Read compiler output from shader_error.txt (written by compile_shader.sh)
    err_path = os.path.join(DIR, "shader_error.txt")
    try:
        with open(err_path) as f:
            raw = f.read().strip()
    except OSError:
        raw = (r.stderr or r.stdout or "compilation failed").strip()
    # Surface the most useful line (first error line, skip the file header)
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln and ("error" in ln.lower() or "warning" in ln.lower()):
            return False, ln[:100]
    return False, raw.splitlines()[0][:100] if raw else "compilation failed"

def show():
    print(DIM + "\u2500" * 36 + RESET)
    for i, l in enumerate(lines):
        print(f"{DIM}{i:2}{RESET}  {l}")
    print(DIM + "\u2500" * 36 + RESET)

def set_chars(s):
    with open(CHARS_FILE, "w") as f:
        f.write(s)
    print(f"{DIM}  chars \u2192 {s}{RESET}")

def set_palette(name):
    with open(PAL_FILE, "w") as f:
        f.write(name)
    print(f"{DIM}  palette \u2192 {name}{RESET}")

# ── examples (C syntax; py_to_c-compatible Python math also accepted live) ───
EXAMPLES = [
    ("moiré wormhole",   ["v = sin(sqrt(cx*cx + cy*cy) / 2.0 - t * 3.0);",
                          "v *= sin(atan2(cy, cx) * 7.0 + t);"]),
    ("acid grid",        ["v = sin(x / 3.0 + sin(y / 4.0 + t));",
                          "v += sin(y / 3.0 + sin(x / 4.0 - t));"]),
    ("breathing spiral", ["v = sin(atan2(cy, cx) * 5.0 - sqrt(cx*cx + cy*cy) / 3.0 + t * 2.0);"]),
    ("zoom tunnel",      ["double r = sqrt(cx*cx + cy*cy) + 0.001;",
                          "v = sin(10.0 / r - t * 4.0) * sin(atan2(cy, cx) * 3.0);"]),
    ("glitch ripple",    ["v = sin(x / 4.0 + sin(t + y / 20.0) * 10.0);",
                          "v += sin(y / 2.0 - t * 2.0) * 0.5;",
                          "v = sin(v * M_PI * 2.0);"]),
]

SHORTCUTS = {"wormhole": 0, "acid": 1, "spiral": 2, "tunnel": 3, "ripple": 4}

def open_editor():
    global lines
    with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
        f.write("\n".join(lines))
        tmp = f.name
    editor = os.environ.get("EDITOR", "nano")
    subprocess.call([editor, tmp])
    with open(tmp) as f:
        raw = f.read()
    os.unlink(tmp)
    new_lines = [l.rstrip() for l in raw.splitlines()
                 if l.strip() and not l.strip().startswith("//")]
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
        print(f"{RED}  empty \u2014 keeping previous{RESET}")

def show_examples():
    print(f"\n{DIM}\u2500\u2500 examples \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{RESET}")
    for name, ex_lines in EXAMPLES:
        print(f"\n  {name}")
        for l in ex_lines:
            print(f"{DIM}    > {RESET}{l}")

# ── startup ───────────────────────────────────────────────────────────────────
write_shader()
print(f"{DIM}  compiling initial shader...{RESET}", end="", flush=True)
ok, _ = try_compile()
print(f" {'ok' if ok else 'failed'}{RESET}")

print()
print("  \u02d6\u207a\u200a\u2027\u208a\u02da\u2665\u02da\u208a\u2027\u200a\u207a\u02d6 CHARTTY LIVE-CODE ASCII RENDERER \u02d6\u207a\u200a\u2027\u208a\u02da\u2665\u02da\u208a\u2027\u200a\u207a\u02d6  ")
print()
print("  Shader variables")
print(f"  {DIM}(x,y)   pixel position   (cx,cy) = centered{RESET}")
print(f"  {DIM}(t)     time             (cols,rows) terminal size{RESET}")
print(f"  {DIM}(v)     brightness 0..1  (c) colour 0..1 (defaults to v){RESET}")
print()
print("  Type C expressions  (math.sin / math.cos auto-translated)")
print()
print("  Commands")
print(f"  {DIM}<enter>  = add line          undo    = remove last line{RESET}")
print(f"  {DIM}list     = show code         clear   = reset{RESET}")
print(f"  {DIM}palette  = show/set palette  chars   = show/set charset{RESET}")
print(f"  {DIM}examples = show presets      edit    = open in $EDITOR{RESET}")
print()
show()

# ── REPL loop ─────────────────────────────────────────────────────────────────
while True:
    try:
        raw = input(f"\n{GREEN}>{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not raw:
        continue
    elif raw == "clear":
        lines = ["v = 0.0;"]
        write_shader()
        try_compile()
        show()
    elif raw == "undo":
        if len(lines) > 1:
            lines.pop()
        write_shader()
        try_compile()
        show()
    elif raw == "list":
        show()
    elif raw == "examples":
        show_examples()
    elif raw == "edit":
        open_editor()
    elif raw.startswith("palette"):
        arg = raw[7:].strip()
        if arg in PALETTES:
            set_palette(arg)
        elif arg == "":
            print(f"{DIM}  palettes:{RESET}")
            for p in PALETTES:
                print(f"{DIM}    palette {p}{RESET}")
        else:
            print(f"{RED}  unknown palette \u2014 try: {' '.join(PALETTES)}{RESET}")
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
                    lines.insert(idx, removed)  # revert
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
        # Translate Python math syntax → C, add semicolon
        c_line = py_to_c(raw)
        lines.append(c_line)
        write_shader()
        ok, err = try_compile()
        if ok:
            print(f"{DIM}  \u2713{RESET}")
            show()
        else:
            lines.pop()
            write_shader()
            try_compile()   # restore previous valid shader
            print(f"{RED}  error: {err}{RESET}")
