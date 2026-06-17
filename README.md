# chartty (𖦹﹏𖦹;)

Live-code ASCII renderer in your terminal. Trigonomatry is your best friend (｡•̀ᴗ-)✧ 

```
v = math.sin(math.sqrt(cx*cx + cy*cy) / 2.0 - t * 3.0)
v *= math.sin(math.atan2(cy, cx) * 7.0 + t)
```


## Installation ദ്ദി ˉ꒳ˉ )✧

```bash
cd chartty
bash install/install.sh
```



## Usage ✎ᝰ.ᐟ⋆⑅˚₊

`chartty` opens two panes: left is renderer, right is live-code-editor

Type trig functions, press enter, generate textures rendered with ASCII chars :3


| Variable | Usage |
|---|---|
| `x`, `y` | pixel position (top-left is 0,0) |
| `cx`, `cy` | centered (`x - cols/2`, `y - rows/2`) |
| `t` | time in seconds |
| `cols`, `rows` | terminal dimensions |
| `v` | brightness 0..1 |
| `c` | color 0..1 (defaults to `v`) |

use `math`, `math.sin`, `math.cos`, `math.sqrt`, `math.pi`, `math.atan2` ...

**Commands**

```
undo            remove last line
clear           reset to blank
list            show current code
del <n>         delete line n
edit            live-edit (^S save, ^C cancel)
examples        show built-in presets
wormhole        moiré wormhole
acid            acid grid
spiral          breathing spiral
groove          wave stretch
tunnel          zoom tunnel
ripple          glitch ripple
palette         list palettes
palette fire    switch palette
chars kawaii    switch character set
```

**Edit mode**

`edit` opens a live-editor session over the current shader. Type to mutate and every keystroke will compile and update the canvas in real-time

- `^S` - save & exit
- `^C` - cancel and revert to pre-edit sahder
- `enter` - newline

**Palettes:** `rainbow` `fire` `plasma` `green` `gold` `fiesta` `mono` `acid` `acid2` `toxic` `lava` `electricity`



## Layout ⊟⊞

`chartty` runs inside a tmux session with two panes: the renderer and the REPL. Default layout = horizontal

Type `layout` in the REPL to flip between:

- **horizontal** — renderer left, editor right
- **vertical**   — renderer top, editor bottom



## How does it work ( •᷄‎ࡇ•᷅ )

1. The renderer calls your *shader* function once per frame, passing numpy arrays for `x` and `y`
2. Math then runs over entire pixel grid once per frame

```
repl.py        →   shader.py   →   renderer.py
(you type)         (your fn)       (numpy + tmux pane)
```



## Requirements ‧₊ ᵎᵎ 🍒 ⋅ ˚✮

- macOS or Linux
- Python 3
- tmux (installed automatically by install.sh)



## License ( ◡̀_◡́)ᕤ

MIT — Entroplay LLC
