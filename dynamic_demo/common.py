"""Angular distance and transcript tokenization."""
import numpy as np

def angular(a, b):
    a, b = np.radians(a), np.radians(b)
    return float(np.degrees(np.arccos(np.clip(np.sin(a[1])*np.sin(b[1]) +
        np.cos(a[1])*np.cos(b[1])*np.cos(a[0]-b[0]), -1., 1.))))

def tokens(text):
    import re
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*", text.lower())
