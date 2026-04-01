# chartty

live-code ASCII animations in your terminal. write math, watch it render.

```
v = sin(sqrt(cx*cx + cy*cy) / 2.0 - t * 3.0);
v *= sin(atan2(cy, cx) * 7.0 + t);
```

the renderer is written in C — shaders compile to native code via `dlopen` hot-swap, so there's no lag even at full terminal size.

---

## install

**dependencies:** `tmux`, `cc` (clang or gcc), `python3`

```bash
git clone https://github.com/YOUR_USERNAME/chartty
cd chartty
./install.sh
```

then run:

```bash
ascii-c
```

to uninstall:

```bash
./uninstall.sh
```

---

## usage

the window splits into two panes. the left pane renders. the right pane is your editor.

type expressions and hit enter. the shader recompiles and hot-swaps instantly.

**available variables**

| variable | meaning |
|---|---|
| `x`, `y` | pixel position (top-left is 0,0) |
| `cx`, `cy` | centered coords (`x - cols/2`, `y - rows/2`) |
| `t` | time, increments each frame |
| `cols`, `rows` | terminal dimensions |
| `v` | brightness output (0..1) |
| `c` | colour index (0..1, defaults to `v`) |

all standard C math functions available: `sin`, `cos`, `sqrt`, `atan2`, `pow`, `fabs`, `M_PI` ...

python-style math also works — `math.sin(` is auto-translated to `sin(`.

**commands**

```
undo          remove last line
clear         reset to blank
list          show current code
del <n>       delete line n
edit          open in $EDITOR
palette       list palettes
palette fire  switch palette
chars ascii   switch character set
examples      show preset shaders
wormhole      load moiré wormhole preset
acid          load acid grid preset
spiral        load breathing spiral preset
tunnel        load zoom tunnel preset
ripple        load glitch ripple preset
```

**palettes:** `rainbow` `fire` `plasma` `ice` `green` `gold` `rose` `neon` `mono`

---

## how it works

```
repl.py          →   shader_body.c   →   compile_shader.sh
(you type here)      (your C body)       (cc -O2 -dynamiclib)
                                              ↓
                                         shader.so
                                              ↓
                                     renderer  (dlopen hot-swap)
                                     one write() per frame
```

shaders are real compiled C. each time you add a line, the REPL wraps your code in a function template, compiles it to a shared library, and the renderer `dlopen`s it. no interpreter overhead in the render loop.

---

## requirements

- macOS or Linux
- clang or gcc
- tmux
- python3 (for the REPL only — the renderer itself is pure C)
