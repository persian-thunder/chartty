#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
SESSION="chartty"
PYTHON="$DIR/.venv/bin/python3"
# editor pane kept at a fixed width so the CHARTTY banner (widest line ~71 cols) never wraps;
# the render pane flexes into whatever width is left.
REPL_COLS=72

# restore terminal state
stty sane 2>/dev/null || true

# Kill all sessions first
tmux kill-session -t "$SESSION" 2>/dev/null
sleep 0.15

tmux new-session -d -s "$SESSION" \
    -e "TERM_PROGRAM=${TERM_PROGRAM:-}" \
    -e "ITERM_SESSION_ID=${ITERM_SESSION_ID:-}" \
    -e "WEZTERM_PANE=${WEZTERM_PANE:-}" \
    -e "WEZTERM_EXECUTABLE=${WEZTERM_EXECUTABLE:-}" \
    "$PYTHON $DIR/src/renderer.py"
tmux set-option -t "$SESSION" allow-passthrough on
tmux set-option -t "$SESSION" mouse on
tmux set-option -t "$SESSION" aggressive-resize on
tmux set-option -t "$SESSION" focus-events on

# wait until session is live
for i in $(seq 1 40); do
    tmux has-session -t "$SESSION" 2>/dev/null && break
    sleep 0.05
done

REPL_PANE=$(tmux split-window -h -l "$REPL_COLS" -t "$SESSION" -P -F '#{pane_id}' \
    -e "TERM_PROGRAM=${TERM_PROGRAM:-}" \
    -e "ITERM_SESSION_ID=${ITERM_SESSION_ID:-}" \
    -e "WEZTERM_PANE=${WEZTERM_PANE:-}" \
    -e "WEZTERM_EXECUTABLE=${WEZTERM_EXECUTABLE:-}" \
    -e "CHARTTY_REPL_COLS=$REPL_COLS" \
    "$PYTHON $DIR/src/repl.py")

# tmux scales panes proportionally on resize, so re-pin the editor width whenever
# the window changes size — keeps the banner from wrapping at any terminal size.
tmux set-hook -t "$SESSION" window-resized "resize-pane -t $REPL_PANE -x $REPL_COLS"

# keep REPL pane open on crash so the traceback stays visible
tmux set-option -p -t "$SESSION" remain-on-exit on

trap "tmux kill-session -t '$SESSION' 2>/dev/null" EXIT
tmux attach -t "$SESSION"
