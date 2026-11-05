"""Write the clip-id subsets used by runners (corpus/subset_<name>.txt) and the job list for
the espeak word-event extraction (corpus/raw/_text/events_jobs.json).
  core   : every full clip, trunc/mid of the 15 brief phrases, silence/noise, 3 pairs per voice
  mini   : full + trunc/mid (espeak175/450, piper) of the brief phrases, silence/noise, 1 pair/voice
  det    : 40 clips for the 3x determinism run (seed 7)
  timing : 60 clips stratified by duration (speech clips only)"""
import json, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in open(ROOT / "corpus/clips.jsonl")]
brief = {f"p{i:03d}" for i in range(15)}
pairs = {}
for r in rows:
    if r["type"] == "pair":
        pairs.setdefault(r["voice"], []).append(r["clip"])


def w(name, ids):
    (ROOT / f"corpus/subset_{name}.txt").write_text("\n".join(ids))
    print(name, len(ids))


w("core", [r["clip"] for r in rows if r["type"] in ("full", "silence", "noise")
           or (r["type"] in ("trunc", "mid") and r["pid"] in brief)] + [c for v in pairs.values() for c in v[:3]])
w("mini", [r["clip"] for r in rows if (r["pid"] in brief and (r["type"] == "full" or (
    r["type"] in ("trunc", "mid") and r["voice"] in ("espeak175", "espeak450", "piper"))))
    or r["type"] in ("silence", "noise")] + [v[0] for v in pairs.values()])
rng = random.Random(7)
by = {}
for r in rows:
    by.setdefault(r["type"], []).append(r["clip"])
w("det", rng.sample(by["full"], 12) + rng.sample(by["trunc"], 12) + rng.sample(by["mid"], 8)
  + by["silence"] + by["noise"] + rng.sample(by["pair"], 4))
rs = sorted([r for r in rows if r["type"] in ("full", "trunc", "mid", "pair")], key=lambda r: r["dur"])
w("timing", [rs[round(i * (len(rs) - 1) / 59)]["clip"] for i in range(60)])
ps = json.loads((ROOT / "phrases.json").read_text())
(ROOT / "corpus/raw/_text/events_jobs.json").write_text(json.dumps(
    [{"key": f"espeak{r}/{p['id']}", "rate": r, "text": p["say"]} for p in ps for r in (175, 300, 450)]))
