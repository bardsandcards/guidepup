"""Decision-rule table: flag "cut off" when k̂_sim < n - t (t = slack in tokens).
Detection = share of trunc clips flagged; false alarm = share of full clips flagged.
With t = 1 a cut after token n-1 can no longer be detected, so detection is also given for
cuts with k <= n-2. Writes tables_decision.md (the six strongest models; rerun with edits to TOP for others)."""
import csv
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = [r for r in csv.DictReader(open(ROOT / "results.csv")) if r["subset"] in ("all", "core", "mini", "turbo")]
core = set((ROOT / "corpus/subset_core.txt").read_text().split())
by = defaultdict(list)
for r in rows:
    if r["clip"] in core:
        by[r["model"]].append(r)
L = ["| model | voice | t | detected (all cuts) | detected (cuts with k ≤ n-2) | false alarm on full |", "|---|---|---|---|---|---|"]
p = lambda a, b: "-" if not b else f"{100*a/b:.0f}%"
TOP = ["parakeet-tdt-0.6b-v2", "parakeet-tdt-0.6b-v3", "fw-small.en", "fw-distil-small.en", "fw-large-v3-turbo", "fw-base.en"]
for m in [m for m in TOP if m in by]:
    rs = by[m]
    for v in ("espeak175", "espeak300", "espeak450", "piper"):
        tr = [r for r in rs if r["voice"] == v and r["type"] == "trunc"]
        fu = [r for r in rs if r["voice"] == v and r["type"] == "full"]
        for t in (0, 1):
            f = lambda r: int(r["k_sim"]) < int(r["n"]) - t
            deep = [r for r in tr if int(r["k"]) <= int(r["n"]) - 2]
            L.append(f"| {m} | {v} | {t} | {p(sum(map(f, tr)), len(tr))} | {p(sum(map(f, deep)), len(deep))} | {p(sum(map(f, fu)), len(fu))} |")
(ROOT / "tables_decision.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
