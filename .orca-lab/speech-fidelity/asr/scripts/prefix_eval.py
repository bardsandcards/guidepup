"""Scores prefix_ctc.py output. k_hat = argmin_j loss(j) - lam*chars(j) - mu*j, with (lam, mu)
fitted on the synthetic corpus only (exact-cut rate), then applied unchanged to the real corpus.

    prefix_eval.py            (reads out/prefix/{synthetic,real}.jsonl, writes tables_prefix.md)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from spoken import spoken  # noqa: E402


def load(name, manifest):
    refs = {json.loads(l)["clip"]: json.loads(l) for l in open(ROOT / manifest)}
    rows = []
    for l in open(ROOT / f"out/prefix/{name}.jsonl"):
        p = json.loads(l)
        m = refs[p["clip"]]
        cum = [0]
        for t in m["ref"]:
            cum.append(cum[-1] + len(spoken(t)))
        p.update(cum=cum, wpm=m.get("wpm"), kind=m.get("kind"))
        rows.append(p)
    return rows


def k_hat(p, lam, mu):
    s = [v - lam * c - mu * j for j, (v, c) in enumerate(zip(p["losses"], p["cum"]))]
    return min(range(len(s)), key=s.__getitem__)


def ok(p, k):
    return k == p["k"] or (p["type"] == "mid" and k == p["k"] + 1)


syn, real = load("synthetic", "corpus/clips.jsonl"), load("real", "corpus/clips_real.jsonl")
grid = [(lam / 4, mu / 2) for lam in range(0, 25) for mu in range(-10, 21)]
lam, mu = max(grid, key=lambda g: sum(ok(p, k_hat(p, *g)) for p in syn))


def pct(a, b):
    return f"{100 * a / b:.0f}% ({a}/{b})" if b else "-"


def table(rows, group):
    g = defaultdict(list)
    for p in rows:
        g[group(p)].append(p)
    lines = ["| group | clips | exact (k, or k+1 mid-word) | within 1 | beyond k+1 | flags 'cut' (k̂<n) | flags 'cut' with slack (k̂<n-1) |",
             "|---|---|---|---|---|---|---|"]
    for name in sorted(g):
        ps = g[name]
        ks = [k_hat(p, lam, mu) for p in ps]
        lines.append("| " + " | ".join([
            name, str(len(ps)),
            pct(sum(ok(p, k) for p, k in zip(ps, ks)), len(ps)),
            pct(sum(abs(k - p["k"]) <= 1 or ok(p, k) for p, k in zip(ps, ks)), len(ps)),
            pct(sum(k > p["k"] + 1 for p, k in zip(ps, ks)), len(ps)),
            pct(sum(k < p["n"] for p, k in zip(ps, ks)), len(ps)),
            pct(sum(k < p["n"] - 1 for p, k in zip(ps, ks)), len(ps)),
        ]) + " |")
    return "\n".join(lines)


def real_group(p):
    if p["kind"] == "CHAR":
        return "CHAR " + p["type"]
    cut = "full" if p["type"] == "full" else ("cut ≤80 ms" if p["heardMs"] <= 80 else "cut >80 ms")
    return f"{cut}, {p['wpm']} wpm"


ms = sorted(p["ms"] for p in syn + real)
md = [f"Fitted on synthetic only: lam={lam} per char, mu={mu} per word.",
      f"Compute per clip (4 threads, CPUs 12-15/16-19): median {ms[len(ms) // 2]} ms, p90 {ms[int(len(ms) * .9)]} ms.",
      "", "Synthetic (fit set), by voice and clip type:", "",
      table(syn, lambda p: f"{p['voice']} {p['type']}"),
      "", "Real Orca sessions (held out):", "", table(real, real_group),
      "", "Unfitted (lam=mu=0), real:", ""]
lam_fit, mu_fit = lam, mu
lam = mu = 0
md.append(table(real, real_group))
lam, mu = lam_fit, mu_fit
(ROOT / "tables_prefix.md").write_text("\n".join(md) + "\n")
print("\n".join(md))
