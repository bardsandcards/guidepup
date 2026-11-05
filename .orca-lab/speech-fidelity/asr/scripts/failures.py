"""Print failure-mode examples per model from results.csv (for REPORT.md)."""
import csv, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = [r for r in csv.DictReader(open(ROOT / "results.csv")) if r["subset"] in ("all", "core", "mini", "sil")]
want = sys.argv[1:] or sorted({r["model"] for r in rows})
for m in want:
    rs = [r for r in rows if r["model"] == m]
    if not rs:
        continue
    print(f"## {m}")
    tail = sorted([r for r in rs if r["tail_hall"] == "1"], key=lambda r: r["tail_hall2"], reverse=True)
    print(f"tail hallucinations ({len(tail)}):")
    for r in tail[:6]:
        print(f"   {'[>=2] ' if r['tail_hall2']=='1' else ''}{r['clip']} k={r['k']} ref='{r['ref']}' hyp='{r['hyp']}'")
    sil = [r for r in rs if r["type"] in ("silence", "noise") and r["nonempty"] == "1"]
    print(f"silence/noise non-empty ({len(sil)}):", "; ".join(f"{r['pid']}={r['hyp']!r}" for r in sil[:8]))
    long = sorted([r for r in rs if r["type"] == "full"], key=lambda r: -int(r["edits"] or 0))[:4]
    print("worst full clips:")
    for r in long:
        print(f"   {r['clip']} edits={r['edits']} ref='{r['ref']}' hyp='{r['hyp'][:120]}'")
    comp = [r for r in rs if r["mid_class"] == "completed"][:3]
    print("mid-word completed e.g.:", "; ".join(f"{r['clip'].split('__',1)[1]} -> {r['hyp']!r}" for r in comp))
    ft = [r for r in rs if r["type"] == "full" and r["flagged_sim"] == "1"][:4]
    print("false 'cut' on full e.g.:", "; ".join(f"{r['clip'].split('__',1)[1]}: '{r['ref']}' -> {r['hyp']!r}" for r in ft))
    print()
