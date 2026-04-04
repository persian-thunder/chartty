#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
CMD="chartty"
RED='\033[31m'; GREEN='\033[32m'; DIM='\033[2m'; RESET='\033[0m'

echo ""
echo "  chartty installer"
echo ""

# ── python3 ───────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "  ${RED}python3 not found${RESET}"
    echo ""
    echo "  macOS:  brew install python3"
    echo "  Linux:  sudo apt install python3"
    echo ""
    exit 1
fi
echo -e "  ${DIM}ok${RESET}   python3"

# ── tmux ──────────────────────────────────────────────────────────────────────
if ! command -v tmux &>/dev/null; then
    echo "  installing tmux..."
    if command -v brew &>/dev/null; then
        brew install tmux
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y tmux
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y tmux
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm tmux
    else
        echo -e "  ${RED}could not install tmux — install it manually and re-run${RESET}"
        exit 1
    fi
fi
echo -e "  ${DIM}ok${RESET}   tmux"

# ── pip + numpy ───────────────────────────────────────────────────────────────
python3 -m ensurepip --quiet 2>/dev/null || true
python3 -m pip install -q -r "$DIR/requirements.txt"
echo -e "  ${DIM}ok${RESET}   numpy"

# ── webcam (optional) ─────────────────────────────────────────────────────────
echo ""
read -r -p "  install webcam support? (~50MB) [y/N] " webcam
if [[ "$webcam" =~ ^[Yy]$ ]]; then
    # install libgl1 on Linux if missing (opencv needs it)
    if [[ "$OSTYPE" == "linux"* ]]; then
        if ! python3 -c "import ctypes; ctypes.CDLL('libGL.so.1')" &>/dev/null; then
            echo "  installing libgl1..."
            if command -v apt-get &>/dev/null; then
                sudo apt-get install -y libgl1 libglib2.0-0
            elif command -v dnf &>/dev/null; then
                sudo dnf install -y mesa-libGL
            elif command -v pacman &>/dev/null; then
                sudo pacman -S --noconfirm mesa
            fi
        fi
    fi
    python3 -m pip install -q -r "$DIR/requirements-webcam.txt"
    echo -e "  ${DIM}ok${RESET}   opencv-python-headless"
fi

# ── chartty command ───────────────────────────────────────────────────────────
WRAPPER="#!/usr/bin/env bash
exec \"$DIR/launch.sh\" \"\$@\"
"

install_cmd() {
    printf '%s' "$WRAPPER" > "$1/$CMD"
    chmod +x "$1/$CMD"
    echo -e "  ${GREEN}ok${RESET}   $1/$CMD"
}

if [ -w "/usr/local/bin" ]; then
    install_cmd "/usr/local/bin"
elif [ -d "$HOME/.local/bin" ]; then
    install_cmd "$HOME/.local/bin"
    echo -e "  ${DIM}note: make sure ~/.local/bin is in your PATH${RESET}"
else
    mkdir -p "$HOME/.local/bin"
    install_cmd "$HOME/.local/bin"
    echo ""
    echo "  add this to your ~/.zshrc or ~/.bashrc:"
    echo -e "  ${DIM}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi

echo ""
echo -e "  ${GREEN}done.${RESET} run:  chartty"
echo ""
