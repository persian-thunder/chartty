#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
SESSION="chartty"
PYTHON="$DIR/.venv/bin/python3"

# Restore terminal state in case a previous tmux session left it in raw mode
stty sane 2>/dev/null || true

# Kill any lingering session and wait for it to fully die before starting fresh
tmux kill-session -t "$SESSION" 2>/dev/null
sleep 0.15

tmux new-session -d -s "$SESSION" \
    -e "TERM_PROGRAM=${TERM_PROGRAM:-}" \
    -e "ITERM_SESSION_ID=${ITERM_SESSION_ID:-}" \
    -e "WEZTERM_PANE=${WEZTERM_PANE:-}" \
    -e "WEZTERM_EXECUTABLE=${WEZTERM_EXECUTABLE:-}" \
    "$PYTHON $DIR/src/renderer.py"
tmux set-option -t "$SESSION" allow-passthrough on

# Wait until the session is confirmed alive instead of a fixed sleep
for i in $(seq 1 40); do
    tmux has-session -t "$SESSION" 2>/dev/null && break
    sleep 0.05
done

tmux split-window -h -p 35 -t "$SESSION" \
    -e "TERM_PROGRAM=${TERM_PROGRAM:-}" \
    -e "ITERM_SESSION_ID=${ITERM_SESSION_ID:-}" \
    -e "WEZTERM_PANE=${WEZTERM_PANE:-}" \
    -e "WEZTERM_EXECUTABLE=${WEZTERM_EXECUTABLE:-}" \
    "$PYTHON $DIR/src/repl.py"

trap "tmux kill-session -t '$SESSION' 2>/dev/null" EXIT
tmux attach -t "$SESSION"
