# Fix: Issue #3 — Cursor flickering and jumping in split pane

## Root cause

Two separate problems were causing the cursor issue reported in issue #3:

### 1. tmux inactive pane cursor (the `|` jumping in the renderer pane)

tmux shows a dim hollow cursor in non-active panes at whatever position that pane's
cursor currently sits. The renderer was moving its cursor constantly — `HOME` to (1,1)
at the start of every frame, then to the status line at the end. The hollow cursor
visibly jumped between those two positions every frame (~30x/sec).

**Fix:** Park the renderer cursor at `\033[1;1H` (top-left) at the end of every frame
write, after all content is rendered. The cursor sits hidden under the first rendered
character and doesn't visibly jump.

Additionally, `HIDE` (`\033[?25l`) was being sent before `RESET` (`\033[0m`) inside the
frame body. `RESET` clears all SGR state, undoing HIDE. Moving HIDE to after the frame
content (after all RESETs) ensures the cursor is actually hidden.

### 2. Frame tearing — rows rendering one after another

The renderer was using `sys.stdout.buffer.raw.write()` which makes a single `write()`
syscall. macOS PTY kernel buffers are ~4KB. A full frame is 50–200KB, so only the first
4KB was written — the rest, including the cursor parking sequence, was silently dropped.
The cursor ended up wherever the truncated write happened to stop.

**Fix:** Switched to `sys.stdout.buffer.write()` + `sys.stdout.buffer.flush()`, which
loops internally until every byte is delivered.

### 3. Frame tearing — partial rendering visible mid-frame (WezTerm / supported terminals)

Even with complete writes, the terminal emulator renders bytes as they arrive. For large
frames this means rows visibly appear one after another.

**Fix:** Synchronized Update Protocol (`\033[?2026h` / `\033[?2026l`) — BSU/ESU. The
terminal buffers the entire frame and renders it atomically. Only applied for terminals
that support it (WezTerm, Kitty, iTerm2). Skipped for Apple_Terminal which does not
support these escapes.

### 4. Performance on Terminal.app

Terminal.app is CPU-rendered and processes ANSI at approximately 50–80KB/sec. A full
frame is ~50–100KB. At 30fps, `flush()` blocks for ~1 second per frame waiting for
Terminal.app to drain its buffer, making the animation appear to update once per second
and the REPL feel unresponsive.

**Fix:** Detect `$TERM_PROGRAM == "Apple_Terminal"` and reduce frame rate to 8fps.
At 8fps, Terminal.app keeps up, `flush()` doesn't block, and the REPL is responsive.
WezTerm and other GPU-rendered terminals stay at 30fps.

---

## Files changed

### `src/renderer.py`

| Change | Why |
|--------|-----|
| Added `BSU` / `ESU` constants, detect `Apple_Terminal` via `$TERM_PROGRAM` | Synchronized updates for supported terminals only |
| Moved `HIDE` to after frame content in the write sequence | `RESET` inside frame body was undoing `HIDE` |
| Added `\033[1;1H` cursor park at end of every frame | Hides tmux inactive pane cursor under content |
| Switched `.raw.write()` → `.write()` + `.flush()` | Ensures complete frame including park sequence is delivered |
| `FRAME_TIME = 1/8` for Apple_Terminal, `1/30` otherwise | Prevents flush() blocking on slow terminal |
| Fixed `POLL_EVERY = 1` → `3` | Was doing file stat checks every frame unnecessarily |

### `launch.sh`

| Change | Why |
|--------|-----|
| Added `tmux set-option -t "$SESSION" allow-passthrough on` | Enables tmux passthrough for terminals that need it |

---

## What still doesn't work on Terminal.app

The REPL cursor (`_`) still flickers in Terminal.app because tmux physically moves the
terminal cursor during every redraw. This is inherent to how Terminal.app + tmux work —
Terminal.app has a single physical cursor that tmux must move to paint content, then
snap back to the REPL prompt. At 8fps this is much less frequent but still visible.

**Recommendation:** Use WezTerm or Kitty. Both are GPU-rendered, support BSU/ESU
synchronized updates, and do not exhibit this cursor behavior.
