"""Import the real-Orca-session corpus (read-only source):
    build_real.py <real-corpus-manifest.jsonl>      (written by .orca-lab/make_manifest.py)
Each WAV (22050 Hz, espeak-ng as played, already cut where Orca interrupted it) is resampled to
16 kHz and padded with 300 ms of silence each side (same as the synthetic corpus) into
corpus/clips/real__<run>__<name>.wav. Manifest: corpus/clips_real.jsonl, with
  type = full | trunc (cut on a word boundary, partialWord null) | mid (cut inside partialWord)
  ref = norm(text), k = len(norm(heardText)) (n for full clips)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audio import load16k, pad, write, SR  # noqa
from textnorm import norm  # noqa

SRC = Path(sys.argv[1])
rows, bad = [], []
for l in open(SRC):
    m = json.loads(l)
    src = Path(m["clip"])
    cid = f"real__{m['run']}__{src.stem}"
    x = pad(load16k(src))
    write(ROOT / f"corpus/clips/{cid}.wav", x)
    ref, heard = norm(m["text"]), norm(m["heardText"])
    if heard != ref[: len(heard)]:
        bad.append((cid, m["text"], m["heardText"]))
    t = "full" if m["outcome"] == "full" else ("mid" if m["partialWord"] else "trunc")
    rows.append({"clip": cid, "dur": round(len(x) / SR, 4), "type": t, "voice": f"real{m['wpm']}",
                 "pid": cid, "text": m["text"], "ref": ref, "n": len(ref),
                 "k": len(ref) if t == "full" else len(heard), "cut": None,
                 "kind": m["kind"], "outcome": m["outcome"], "wpm": m["wpm"], "heardMs": m["heardMs"],
                 "durMs": m["durMs"], "heardText": m["heardText"], "partialWord": m["partialWord"],
                 "src": str(src), "test": m["test"], "run": m["run"]})
with open(ROOT / "corpus/clips_real.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(rows), "clips;", len(bad), "where norm(heardText) is not a prefix of norm(text):")
for b in bad[:10]:
    print("  ", b)
