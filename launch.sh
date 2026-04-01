#!/bin/bash
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
SESSION="chartty"

# ── build renderer if stale ─────────────────────────────────────────────────
if [ ! -f "$DIR/renderer" ] || [ "$DIR/renderer.c" -nt "$DIR/renderer" ]; then
    echo "Building renderer..."
    make -C "$DIR" renderer || { echo "Build failed. Run: make -C $DIR"; exit 1; }
fi

# ── compile initial shader if shader.so is missing ──────────────────────────
if [ ! -f "$DIR/shader.so" ]; then
    bash "$DIR/compile_shader.sh" 2>/dev/null || true
fi

# ── launch tmux session ──────────────────────────────────────────────────────
tmux kill-session -t $SESSION 2>/dev/null

tmux new-session  -d -s $SESSION             "$DIR/renderer"
tmux split-window    -h -p 35 -t $SESSION    "python3 $DIR/repl.py"

tmux attach -t $SESSION
