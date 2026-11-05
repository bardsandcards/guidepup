"""Extra silence/noise clips for the hallucination check (separate manifest
corpus/clips_sil.jsonl so the main 'all' subset stays the same for every model).
20 clips: {1, 3, 5 s} x {digital zero, dither -90 dBFS, white -60, -50, -40 dBFS, pink -50 dBFS}
x seeds where random (white/pink at 3 s get 2 seeds)."""
import json, sys
import numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audio import write, SR  # noqa


def pink(n, rng):
    f = np.fft.rfftfreq(n)
    spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    spec[1:] /= np.sqrt(f[1:]); spec[0] = 0
    x = np.fft.irfft(spec, n)
    return x / np.sqrt((x ** 2).mean())


rows = []
for dur in (1, 3, 5):
    n = dur * SR
    kinds = [("zero", None, 0), ("dither", -90, 0), ("white", -60, 0), ("white", -50, 0), ("white", -40, 0), ("pink", -50, 0)]
    if dur == 3:
        kinds += [("white", -50, 1), ("pink", -50, 1)]
    for kind, db, seed in kinds:
        rng = np.random.default_rng(1000 * dur + seed + (db or 0) + 7)
        if kind == "zero":
            x = np.zeros(n)
        elif kind == "pink":
            x = pink(n, rng) * 10 ** (db / 20)
        else:
            x = rng.standard_normal(n) * 10 ** (db / 20)
        cid = f"sil2__{kind}{'' if db is None else -db}_{dur}s_s{seed}"
        write(ROOT / f"corpus/clips/{cid}.wav", x.astype("float32"))
        rows.append({"clip": cid, "dur": float(dur), "type": "silence" if kind in ("zero", "dither") else "noise",
                     "voice": "none", "pid": cid.split("__")[1], "ref": [], "n": 0, "k": 0, "cut": None, "text": ""})
with open(ROOT / "corpus/clips_sil.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(rows))
