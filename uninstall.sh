#!/bin/bash
# uninstall.sh — removes the ascii-c command

CMD="ascii-c"
LOCATIONS=("/usr/local/bin/$CMD" "$HOME/.local/bin/$CMD")
FOUND=0

for loc in "${LOCATIONS[@]}"; do
    if [ -f "$loc" ]; then
        rm "$loc"
        echo "removed: $loc"
        FOUND=1
    fi
done

[ "$FOUND" = "0" ] && echo "ascii-c not found in /usr/local/bin or ~/.local/bin"
