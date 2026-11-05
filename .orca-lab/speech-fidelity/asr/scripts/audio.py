import numpy as np, soundfile as sf
from scipy.signal import resample_poly
from math import gcd

SR = 16000
PAD = 0.300


def load16k(path):
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        g = gcd(SR, sr)
        x = resample_poly(x, SR // g, sr // g).astype("float32")
    return x


def trim(x, thresh_db=-50.0, frame=0.010):
    """Strip leading/trailing TTS silence: first/last 10 ms frame above -50 dBFS RMS."""
    n = int(frame * SR)
    if len(x) < n:
        return x
    frames = len(x) // n
    rms = np.sqrt((x[: frames * n].reshape(frames, n) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    on = np.where(db > thresh_db)[0]
    if len(on) == 0:
        return x[:0]
    return x[on[0] * n : (on[-1] + 1) * n]


def pad(x, before=PAD, after=PAD):
    return np.concatenate([np.zeros(int(before * SR), "float32"), x, np.zeros(int(after * SR), "float32")])


def write(path, x):
    sf.write(str(path), x, SR, subtype="PCM_16")
