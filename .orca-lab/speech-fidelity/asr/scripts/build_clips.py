"""Stage 3: cut clips from the aligned full utterances and write corpus/clips.jsonl.

Clip types:
  full   - whole utterance, 300 ms silence each side
  trunc  - cut at canonical token boundary k (midpoint of the gap between the aligned end of the
           last spoken word of token k and the aligned start of the next spoken word), abrupt cut
           (no fade, like a speechd STOP), then 300 ms silence
  mid    - cut halfway through the next spoken word (the first word of token k+1), same padding
  silence/noise - 3 s digital zero, 3 s dither (-90 dBFS), 3 s white noise at -50 and -40 dBFS RMS
  pair   - two full utterances (TTS padding stripped) with a 150 ms gap, 300 ms each side
At most 6 boundaries per (phrase, voice), evenly spaced, when a phrase has more.
"""
import json, re, sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audio import load16k, pad, write, SR, PAD  # noqa
from textnorm import norm  # noqa

VOICES = ["espeak175", "espeak300", "espeak450", "piper"]
MAXK = 6


def chunk_map(say):
    """[(chunk_text, [spoken word indices])]"""
    out, i = [], 0
    for c in say.split():
        ws = re.findall(r"[a-z']+", c.lower())
        out.append((c, list(range(i, i + len(ws)))))
        i += len(ws)
    return out


def boundaries(say):
    """{k: chunk index c whose end is canonical boundary k} for 1 <= k < n."""
    T = norm(say)
    cm = chunk_map(say)
    res = {}
    for c in range(len(cm) - 1):
        if not cm[c][1]:
            continue
        P = norm(" ".join(x for x, _ in cm[: c + 1]))
        k = len(P)
        if 0 < k < len(T) and P == T[:k]:
            res[k] = c  # later chunk wins (e.g. trailing punctuation-only chunks)
    return T, cm, res


def pick(ks, m=MAXK):
    ks = sorted(ks)
    if len(ks) <= m:
        return ks
    idx = np.round(np.linspace(0, len(ks) - 1, m)).astype(int)
    return sorted(set(ks[i] for i in idx))


def main():
    phrases = json.loads((ROOT / "phrases.json").read_text())
    al = json.loads((ROOT / "corpus/align.json").read_text())
    out = ROOT / "corpus/clips"
    out.mkdir(parents=True, exist_ok=True)
    rows = []

    def emit(cid, x, **meta):
        write(out / f"{cid}.wav", x)
        rows.append({"clip": cid, "dur": round(len(x) / SR, 4), **meta})

    for v in VOICES:
        for p in phrases:
            x = load16k(ROOT / f"corpus/full/{v}/{p['id']}.wav")
            words = al[f"{v}/{p['id']}"]["words"]
            T, cm, bd = boundaries(p["say"])
            n = len(T)
            # canonical token end times on the full clip
            tok_end = {}
            for k, c in bd.items():
                tok_end[k] = words[cm[c][1][-1]][2]
            tok_end[n] = words[-1][2]
            base = dict(voice=v, pid=p["id"], text=p["text"], ref=T, n=n)
            emit(f"{v}__{p['id']}__full", x, type="full", k=n, cut=None,
                 tok_end={str(k): round(t, 3) for k, t in sorted(tok_end.items())}, **base)
            for k in pick(bd):
                c = bd[k]
                end_w = words[cm[c][1][-1]]
                nxt = next(cm[j][1][0] for j in range(c + 1, len(cm)) if cm[j][1])
                nw = words[nxt]
                cut = (end_w[2] + nw[1]) / 2
                emit(f"{v}__{p['id']}__trunc{k}", pad(x[: int(cut * SR)], 0, PAD), type="trunc",
                     k=k, cut=round(cut, 3), word_end=round(end_w[2], 3), next_start=round(nw[1], 3), **base)
                mid = (nw[1] + nw[2]) / 2
                emit(f"{v}__{p['id']}__mid{k}", pad(x[: int(mid * SR)], 0, PAD), type="mid",
                     k=k, cut=round(mid, 3), partial_word=nw[0], **base)

    # silence / noise (voice independent)
    rng = np.random.default_rng(20261101)
    n3 = 3 * SR
    emit("sil__zero", np.zeros(n3, "float32"), type="silence", voice="none", pid="sil_zero", ref=[], n=0, k=0, cut=None, text="")
    emit("sil__dither", (rng.standard_normal(n3) * 10 ** (-90 / 20)).astype("float32"), type="silence", voice="none", pid="sil_dither", ref=[], n=0, k=0, cut=None, text="")
    for db in (-50, -40):
        emit(f"noise__m{-db}", (rng.standard_normal(n3) * 10 ** (db / 20)).astype("float32"), type="noise", voice="none", pid=f"noise_m{-db}", ref=[], n=0, k=0, cut=None, text="")

    # back-to-back pairs: consecutive brief/extra phrases with >= 2 tokens
    cand = [p for p in phrases if p["source"] in ("brief", "extra") and len(norm(p["say"])) >= 2]
    pairs = [(cand[i], cand[i + 1]) for i in range(0, min(len(cand) - 1, 24), 2)]
    gap = np.zeros(int(0.150 * SR), "float32")
    for v in VOICES:
        for a, b in pairs:
            xa = load16k(ROOT / f"corpus/full/{v}/{a['id']}.wav")[int(PAD * SR): -int(PAD * SR)]
            xb = load16k(ROOT / f"corpus/full/{v}/{b['id']}.wav")[int(PAD * SR): -int(PAD * SR)]
            ra, rb = norm(a["say"]), norm(b["say"])
            emit(f"{v}__{a['id']}+{b['id']}__pair", pad(np.concatenate([xa, gap, xb])), type="pair",
                 voice=v, pid=f"{a['id']}+{b['id']}", text=a["text"] + " | " + b["text"],
                 ref=ra + rb, n=len(ra) + len(rb), k=len(ra), cut=None)

    with open(ROOT / "corpus/clips.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    from collections import Counter
    print(Counter(r["type"] for r in rows), "total", len(rows),
          "audio %.1f min" % (sum(r["dur"] for r in rows) / 60))


if __name__ == "__main__":
    main()
