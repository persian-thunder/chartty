import math

NAMES = [
    "rainbow", "fire", "plasma", "green", "gold", "mono",
    "fiesta", "acid", "acid2", "toxic", "lava", "electricity",
]

PALETTES = {
    "acid2": [
        (  0,   0,   0),
        (  7,  88,   0),
        (137, 255,   0),
        (200, 212, 138),
        (253, 255,   0),
    ],
    "fiesta": [
        (255, 190,  11),
        (251,  86,   7),
        (255,   0, 110),
        (131,  56, 236),
        ( 58, 134, 255),
    ],
    "toxic": [
        (  0,   0,   0),
        ( 10,  40,   0),
        ( 60, 180,   0),
        (180, 255,   0),
        (220, 255,  50),
    ],
    "lava": [
        (  0,   0,   0),
        (120,   0,   0),
        (255,  40,   0),
        (255, 160,   0),
        (255, 255, 200),
    ],
    "electricity": [
        (  0,   0,   0),
        ( 20,   0,  80),
        (  0,  60, 255),
        (100, 200, 255),
        (255, 255, 255),
    ],
}

def gradient(stops, n):
    seg = len(stops) - 1
    pos = n * seg
    low = min(int(pos), seg - 1)
    hi  = low + 1
    t   = pos - low

    r = int(stops[low][0] + (stops[hi][0] - stops[low][0]) * t)
    g = int(stops[low][1] + (stops[hi][1] - stops[low][1]) * t)
    b = int(stops[low][2] + (stops[hi][2] - stops[low][2]) * t)

    return r, g, b

def hsv(h, s, v):
    h = h % 1.0; i = int(h * 6); f = h * 6 - i
    p, q, t2 = v*(1-s), v*(1-f*s), v*(1-(1-f)*s)
    r, g, b = [(v,t2,p),(q,v,p),(p,v,t2),(p,q,v),(t2,p,v),(v,p,q)][i % 6]
    return int(r*255), int(g*255), int(b*255)

def color(name, n):
    if name in PALETTES:
        return gradient(PALETTES[name], n)
    if name == "green":
        return 0, int(30 + n*225), int(n*40)
    if name == "fire":
        r = min(255, int(n*3*255))
        g = min(255, max(0, int((n-.33)*3*255)))
        b = min(255, max(0, int((n-.66)*3*255)))
        return r, g, b
    if name == "rainbow":
        return hsv(n * 0.85, 1.0, 1.0)
    if name == "plasma":
        r = int(128 + 127*math.sin(n*math.pi*2))
        g = int(128 + 127*math.sin(n*math.pi*2 + 2.094))
        b = int(128 + 127*math.sin(n*math.pi*2 + 4.189))
        return r, g, b
    if name == "gold":
        return min(255, int(n*2*255)), int(n*180), int(n*20)
    if name == "mono":
        v = int(n * 255)
        return v, v, v
    if name == "acid":
        h = 0.25 + 0.12 * math.sin(n * math.pi * 4)
        return hsv(h, 1.0, 0.2 + 0.8 * n)
    return hsv(n * 0.85, 1.0, 1.0)
