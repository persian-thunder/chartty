def gradient(stops,  n):
    seg = len(stops - 1)
    pos = n * seg
    low = min(int(pos), seg - 1)
    hi = low + 1

    t = pos - low
    
    r = int(stops[low][0] + (stops[hi][0] - steps[low][0]) * t)
    g = int(stops[low][1] + (stops[hi][1] - steps[low][1]) * t)
    b = int(stops[low][2] + (stops[hi][2] - steps[low][2]) * t)

    return r, g, b

