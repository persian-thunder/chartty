#!/usr/bin/env bash
# uninstall.sh — removes the chartty command

CMD="chartty"
LOCATIONS=("/usr/local/bin/$CMD" "$HOME/.local/bin/$CMD")
FOUND=0

for loc in "${LOCATIONS[@]}"; do
    if [ -f "$loc" ]; then
        rm "$loc"
        echo "removed: $loc"
        FOUND=1
    fi
done

[ "$FOUND" = "0" ] && echo "chartty not found in /usr/local/bin or ~/.local/bin"
