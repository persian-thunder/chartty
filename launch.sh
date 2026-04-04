#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
SESSION="chartty"

tmux kill-session -t $SESSION 2>/dev/null

tmux new-session  -d -s $SESSION             "python3 $DIR/renderer.py"
tmux split-window    -h -p 35 -t $SESSION    "python3 $DIR/repl.py"

tmux attach -t $SESSION
