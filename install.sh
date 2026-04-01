#!/bin/bash
# install.sh — builds Chartty and installs the ascii-c command

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
CMD="ascii-c"
RED='\033[31m'; GREEN='\033[32m'; DIM='\033[2m'; RESET='\033[0m'

echo ""
echo "  chartty installer"
echo ""

# ── check dependencies ───────────────────────────────────────────────────────
echo "  checking dependencies..."
MISSING=0
for dep in tmux cc python3; do
    if command -v "$dep" &>/dev/null; then
        echo -e "  ${DIM}ok${RESET}   $dep"
    else
        echo -e "  ${RED}missing${RESET}  $dep"
        MISSING=1
    fi
done

if [ "$MISSING" = "1" ]; then
    echo ""
    echo -e "  ${RED}install missing dependencies and re-run${RESET}"
    echo ""
    echo "  macOS:  brew install tmux"
    echo "  Linux:  sudo apt install tmux build-essential python3"
    exit 1
fi

# ── build renderer ───────────────────────────────────────────────────────────
echo ""
echo "  building renderer..."
make -C "$DIR" renderer
echo -e "  ${GREEN}ok${RESET}   renderer"

# ── compile initial shader ───────────────────────────────────────────────────
echo "  compiling shader..."
bash "$DIR/compile_shader.sh" 2>/dev/null && echo -e "  ${GREEN}ok${RESET}   shader.so" || echo -e "  ${DIM}skipped (will compile on first run)${RESET}"

# ── write ascii-c wrapper ────────────────────────────────────────────────────
WRAPPER="#!/bin/bash
exec \"$DIR/launch.sh\" \"\$@\"
"

install_cmd() {
    local dest="$1/$CMD"
    printf '%s' "$WRAPPER" > "$dest"
    chmod +x "$dest"
    echo -e "  ${GREEN}ok${RESET}   $dest"
}

echo ""
echo "  installing ascii-c..."

if [ -w "/usr/local/bin" ]; then
    install_cmd "/usr/local/bin"
    INSTALLED_PATH="/usr/local/bin/$CMD"
elif [ -d "$HOME/.local/bin" ]; then
    install_cmd "$HOME/.local/bin"
    INSTALLED_PATH="$HOME/.local/bin/$CMD"
    echo -e "  ${DIM}note: make sure ~/.local/bin is in your PATH${RESET}"
else
    mkdir -p "$HOME/.local/bin"
    install_cmd "$HOME/.local/bin"
    INSTALLED_PATH="$HOME/.local/bin/$CMD"
    echo ""
    echo "  add this to your ~/.zshrc or ~/.bashrc:"
    echo -e "  ${DIM}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi

echo ""
echo -e "  ${GREEN}done.${RESET} run:  ascii-c"
echo ""
