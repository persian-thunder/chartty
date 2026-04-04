def value(x, y, t, cols, rows):
    cx = x - cols / 2
    cy = y - rows / 2
    v = 0.0
    v = math.sin(math.sqrt(cx*cx + cy*cy) / 2.0 - t * 3.0)
    v *= math.sin(math.atan2(cy, cx) * 1.0 + t)
    c = v
    return (v, c)
