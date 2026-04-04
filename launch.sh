#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
SESSION="chartty"
PYTHON="$DIR/.venv/bin/python3"

tmux kill-session -t $SESSION 2>/dev/null

tmux new-session  -d -s $SESSION             "$PYTHON $DIR/src/renderer.py"
tmux split-window    -h -p 35 -t $SESSION    "$PYTHON $DIR/src/repl.py"

tmux attach -t $SESSION
