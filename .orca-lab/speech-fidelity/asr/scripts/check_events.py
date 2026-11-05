"""Compare aligner-derived cut times with espeak-ng's own WORD events (corpus/raw/_events.json).
Writes corpus/event_check.json and corpus/event_check_table.md."""
import json, re, sys
import numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audio import load16k, trim, SR, PAD  # noqa

ev = json.loads((ROOT / "corpus/raw/_events.json").read_text())
al = json.loads((ROOT / "corpus/align.json").read_text())
ph = {p["id"]: p for p in json.loads((ROOT / "phrases.json").read_text())}
clips = [json.loads(l) for l in open(ROOT / "corpus/clips.jsonl")]
lead = {}
res = []
for c in clips:
    if c["type"] != "trunc" or not c["voice"].startswith("espeak"):
        continue
    key = f"{c['voice']}/{c['pid']}"
    if key not in lead:
        x = load16k(ROOT / f"corpus/raw/{key}.wav")
        y = trim(x)
        # leading samples removed by trim
        n = 160
        fr = len(x) // n
        rms = np.sqrt((x[: fr * n].reshape(fr, n) ** 2).mean(1) + 1e-12)
        on = np.where(20 * np.log10(rms) > -50)[0]
        lead[key] = on[0] * n / SR
    say = ph[c["pid"]]["say"]
    # char offset of each whitespace chunk
    starts = [m.start() for m in re.finditer(r"\S+", say)]
    evs = [(w["text_position"] - 1, PAD + w["audio_ms"] / 1000 - lead[key]) for w in ev[key]["words"]]
    # the event whose text position is the first one >= next_start chunk char offset
    words = al[key]["words"]
    nxt_t = c["next_start"]
    # find chunk index of the next spoken word: count spoken words
    sw = 0; nxt_chunk = None
    for ci, m in enumerate(re.finditer(r"\S+", say)):
        k = len(re.findall(r"[a-z']+", m.group().lower()))
        if k and abs(words[sw][1] - nxt_t) < 1e-3 and nxt_chunk is None:
            nxt_chunk = ci
        sw += k
    if nxt_chunk is None:
        continue
    off = starts[nxt_chunk]
    cand = [t for pos, t in evs if pos >= off - 1]
    if not cand:
        continue
    ev_next = cand[0]
    res.append({"clip": c["clip"], "voice": c["voice"], "cut": c["cut"], "align_next": nxt_t, "ev_next": ev_next,
                "cut_minus_ev": c["cut"] - ev_next, "align_minus_ev": nxt_t - ev_next})
(ROOT / "corpus/event_check.json").write_text(json.dumps(res, indent=0))
L = []
for v in ("espeak175", "espeak300", "espeak450"):
    d = np.array([r["cut_minus_ev"] for r in res if r["voice"] == v]) * 1000
    a = np.array([r["align_minus_ev"] for r in res if r["voice"] == v]) * 1000
    L.append(f"| {v} | {len(d)} | {np.median(a):+.0f} | {np.median(d):+.0f} | {np.percentile(d,10):+.0f} / {np.percentile(d,90):+.0f} | {(d <= 20).mean()*100:.0f}% | {(d > 40).mean()*100:.0f}% |")
(ROOT / "corpus/event_check_table.md").write_text("\n".join(L))
print("\n".join(L))
