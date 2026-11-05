"""Tables for the real-Orca-session corpus (subset 'real' in results.csv) -> tables_real.md.
clean match: match plus no extra (non-similar) words, except one guess at a partial word.
match: full clip -> k̂_sim == n; cut clip -> k̂_sim == k, or k+1 when a partial word was
playing, and no exact hit beyond k+1 (i.e. nothing from the unplayed rest of `text`)."""
import csv, json, sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from score import align  # noqa
meta = {json.loads(l)["clip"]: json.loads(l) for l in open(ROOT / "corpus/clips_real.jsonl")}
rows = [r for r in csv.DictReader(open(ROOT / "results.csv")) if r["subset"] == "real"]
by = defaultdict(list)
for r in rows:
    by[r["model"]].append(r)


def match(r):
    m = meta[r["clip"]]
    ks = int(r["k_sim"] or 0)
    if r["type"] == "full":
        return ks == int(r["n"])
    ok = ks == int(r["k"]) or (m["partialWord"] and ks == int(r["k"]) + 1)
    return ok and r["tail_hall"] != "1"


def clean(r):
    """match, and every hypothesis token is an exact hit or a character-similar substitution
    (no extra words such as a spurious "Yeah." on a near-empty clip). One dissimilar token is
    allowed when a partial word was playing (a guess at it)."""
    if not match(r):
        return False
    hyp, ref = r["hyp_norm"].split(), r["ref"].split()
    ops, _ = align(hyp, ref)
    extra = sum(1 for op, hi, ri in ops if hi is not None and not (
        op == "hit" or (op == "sub" and SequenceMatcher(None, hyp[hi], ref[ri]).ratio() >= 0.5)))
    return extra <= (1 if meta[r["clip"]]["partialWord"] else 0)  # one guess allowed for a partial word


p = lambda a, b: "-" if not b else f"{100 * a / b:.0f}% ({a}/{b})"
L = ["| model | group | clips | match | clean match (no extra words) | non-empty output (normalised / raw incl. Um, Uh) | k̂_sim exact | within 1 | any hit beyond k+1 | ≥2 hits beyond k+1 (completion) | false 'cut' (full only) |",
     "|---|---|---|---|---|---|---|---|---|---|---|"]
groups = [
    ("all", lambda m: True),
    ("full, 170 wpm, SPEAK", lambda m: m["outcome"] == "full" and m["wpm"] == 170 and m["kind"] == "SPEAK"),
    ("full, 449 wpm, SPEAK", lambda m: m["outcome"] == "full" and m["wpm"] == 449),
    ("full, CHAR", lambda m: m["outcome"] == "full" and m["kind"] == "CHAR"),
    ("cut >80 ms, 170 wpm, SPEAK", lambda m: m["outcome"] == "cut" and m["heardMs"] > 80 and m["wpm"] == 170 and m["kind"] == "SPEAK"),
    ("cut >80 ms, 449 wpm, SPEAK", lambda m: m["outcome"] == "cut" and m["heardMs"] > 80 and m["wpm"] == 449),
    ("cut >80 ms, CHAR", lambda m: m["outcome"] == "cut" and m["heardMs"] > 80 and m["kind"] == "CHAR"),
    ("cut ≤80 ms (near-empty), 170 wpm, SPEAK", lambda m: m["outcome"] == "cut" and m["heardMs"] <= 80 and m["wpm"] == 170 and m["kind"] == "SPEAK"),
    ("cut ≤80 ms (near-empty), 449 wpm, SPEAK", lambda m: m["outcome"] == "cut" and m["heardMs"] <= 80 and m["wpm"] == 449),
    ("cut ≤80 ms (near-empty), CHAR", lambda m: m["outcome"] == "cut" and m["heardMs"] <= 80 and m["kind"] == "CHAR"),
]
for name, rs in by.items():
    for g, f in groups:
        sel = [r for r in rs if f(meta[r["clip"]])]
        if not sel:
            continue
        n = len(sel)
        cut = [r for r in sel if r["type"] != "full"]
        full = [r for r in sel if r["type"] == "full"]
        L.append(f"| {name} | {g} | {n} | {p(sum(match(r) for r in sel), n)} | {p(sum(clean(r) for r in sel), n)} | {p(sum(r['nonempty'] == '1' for r in sel), n)} / {p(sum(bool(r['hyp'].strip()) for r in sel), n)} | "
                 f"{p(sum(r['exact_sim'] == '1' for r in sel), n)} | {p(sum(r['within1_sim'] == '1' for r in sel), n)} | "
                 f"{p(sum(r['tail_hall'] == '1' for r in cut), len(cut))} | {p(sum(r['tail_hall2'] == '1' for r in cut), len(cut))} | "
                 f"{p(sum(r['flagged_sim'] == '1' for r in full), len(full))} |")
(ROOT / "tables_real.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
# what models say on near-empty clips
L += ["", "Most common raw outputs on near-empty cuts (heardMs <= 80):", ""]
from collections import Counter
for name, rs in by.items():
    c = Counter(r["hyp"].strip() or "(empty)" for r in rs if meta[r["clip"]]["outcome"] == "cut" and meta[r["clip"]]["heardMs"] <= 80)
    L.append(f"- {name}: " + ", ".join(f"{h!r} x{v}" for h, v in c.most_common(6)))
(ROOT / "tables_real.md").write_text("\n".join(L) + "\n")
# examples
for name, rs in by.items():
    print(f"\n## {name} examples")
    bad = [r for r in rs if not clean(r)]
    for r in bad[:12]:
        m = meta[r["clip"]]
        print(f"  {m['outcome']} {m['wpm']} {m['kind']} heardMs={m['heardMs']:.0f} text={m['text']!r} heard={m['heardText']!r} partial={m['partialWord']!r} -> hyp={r['hyp']!r}")
    comp = [r for r in rs if r["tail_hall2"] == "1"]
    for r in comp[:6]:
        m = meta[r["clip"]]
        print(f"  COMPLETION {m['wpm']} text={m['text']!r} heard={m['heardText']!r} -> hyp={r['hyp']!r}")
