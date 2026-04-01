#!/bin/bash
# compile_shader.sh — wraps shader_body.c in a full C function and compiles to shader.so
# Called by repl.py whenever the user modifies their shader code.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
BODY="$DIR/shader_body.c"
FULL="$DIR/shader_full.c"
OUT="$DIR/shader.so"
ERR="$DIR/shader_error.txt"

# Create a default body if missing
if [ ! -f "$BODY" ]; then
    printf '    v = 0.0;\n' > "$BODY"
fi

# ── generate full shader source from template + user body ──────────────────
cat > "$FULL" << 'TEMPLATE_END'
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#ifndef M_E
#define M_E  2.71828182845904523536
#endif

static inline double clamp01(double x) {
    return x < 0.0 ? 0.0 : (x > 1.0 ? 1.0 : x);
}

/* Exported shader entry point — called once per pixel per frame.
 * Available variables: x, y, t, cols, rows, cx (=x-cols/2), cy (=y-rows/2)
 * Set v (brightness 0..1) and optionally c (colour 0..1, defaults to v).
 * All standard C math functions (sin, cos, sqrt, atan2, pow, fabs …) available.
 */
void shader(double x, double y, double t, int cols, int rows,
            double *v_out, double *c_out)
{
    double cx = x - cols * 0.5;
    double cy = y - rows * 0.5;
    double v  = 0.0;

TEMPLATE_END

# append user body
cat "$BODY" >> "$FULL"

cat >> "$FULL" << 'TEMPLATE_END'

    double c = v;   /* default: colour tracks brightness; user can override */
    *v_out = clamp01(v);
    *c_out = clamp01(c);
}
TEMPLATE_END

# ── platform-specific shared-library flags ──────────────────────────────────
if [[ "$(uname)" == "Darwin" ]]; then
    SHARED_FLAGS="-dynamiclib -undefined dynamic_lookup"
else
    SHARED_FLAGS="-shared -fPIC"
fi

# ── compile (write to .tmp first for atomic rename) ──────────────────────────
if cc -O2 -fPIC $SHARED_FLAGS -o "${OUT}.tmp" "$FULL" -lm 2>"$ERR"; then
    mv "${OUT}.tmp" "$OUT"
    rm -f "$ERR"
    exit 0
else
    rm -f "${OUT}.tmp"
    # ERR file now contains the compiler output — renderer will display it
    exit 1
fi
