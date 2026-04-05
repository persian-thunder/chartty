# chartty (𖦹﹏𖦹;)

Live-code ASCII  renderer in your terminal. Trigonomatry is your best friend here (｡•̀ᴗ-)✧ 

```
v = math.sin(math.sqrt(cx*cx + cy*cy) / 2.0 - t * 3.0)
v *= math.sin(math.atan2(cy, cx) * 7.0 + t)
```

---

## Installation ദ്ദി ˉ꒳ˉ )✧

```bash
cd chartty
bash install.sh
```

---

## Usage ✎ᝰ.ᐟ⋆⑅˚₊

`chartty` opens two panes. Left is renderer, right is live editor.

Type  trigonometric functions, press enter, watch magic happen in real-time.


| Variable | Purpose |
|---|---|
| `x`, `y` | pixel position (top-left is 0,0) |
| `cx`, `cy` | centered (`x - cols/2`, `y - rows/2`) |
| `t` | time in seconds |
| `cols`, `rows` | terminal dimensions |
| `v` | brightness 0..1 |
| `c` | color 0..1 (defaults to `v`) |

use anything from `math`, `math.sin`, `math.cos`, `math.sqrt`, `math.pi`, `math.atan2` ...

**Commands**

```
undo            remove last line
clear           reset to blank
list            show current code
del <n>         delete line n
edit            open in $EDITOR
examples        show built-in presets
wormhole        moiré wormhole
acid            acid grid
spiral          breathing spiral
tunnel          zoom tunnel
ripple          glitch ripple
palette         list palettes
palette fire    switch palette
chars kawaii     switch character set
```

**palettes:** `rainbow` `fire` `plasma` `ice` `green` `gold` `rose` `fiesta` `mono`

---


## How does it work ( •᷄‎ࡇ•᷅ )

The renderer calls your *shader* function once per frame, passing numpy arrays for `x` and `y`. Math runs over entire pixel grid once per frame. Frames build at ~60fps.

```
repl.py        →   shader.py   →   renderer.py
(you type)         (your fn)       (numpy + tmux pane)
```

---

## Requirements ‧₊ ᵎᵎ 🍒 ⋅ ˚✮

- macOS or Linux
- Python 3
- tmux (installed automatically by install.sh)