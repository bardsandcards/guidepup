"""Build summary tables from results.csv + timing/determinism outputs.
Writes summary.csv and tables.md (markdown, pasted into REPORT.md)."""
import csv, glob, json, statistics as st, subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = ["espeak175", "espeak300", "espeak450", "piper"]


def size_mb(spec):
    files = []
    for pat in spec.get("files", []):
        files += glob.glob(str(ROOT / pat))
    if "file_glob" in spec:
        files += glob.glob(str(ROOT / "models/hf/hub/models--ggerganov--whisper.cpp/snapshots/*/" / Path(spec["file_glob"])))
    if not files:
        return None
    out = subprocess.run(["du", "-scLb", *files], capture_output=True, text=True).stdout.split("\n")
    tot = [l for l in out if l.endswith("total")]
    return round(int(tot[0].split()[0]) / 1e6) if tot else None


def rate(rows, f):
    v = [int(r[f]) for r in rows if r.get(f) not in ("", None)]
    return (sum(v) / len(v), len(v)) if v else (None, 0)


def pct(x):
    return "-" if x[0] is None else f"{100 * x[0]:.0f}%"


def wer(rows):
    e = sum(int(r["edits"]) for r in rows if r["edits"] != "")
    n = sum(int(r["ref_len"]) for r in rows if r["ref_len"] != "")
    return e / n if n else None


def timing(name):
    p = ROOT / f"out/timing/{name}.jsonl"
    if not p.exists():
        return None
    lines = [json.loads(l) for l in open(p)]
    meta = [l["meta"] for l in lines if "meta" in l]
    recs = [l for l in lines if "meta" not in l]
    if not meta or not recs:
        return None
    rtf = sum(r["t"] for r in recs) / sum(r["dur"] for r in recs)
    short = [r["t"] for r in recs if r["dur"] < 1.2]
    return {"rtf": rtf, "med_lat": st.median(r["t"] for r in recs), "short_lat": st.median(short) if short else None,
            "load": meta[0]["load_s"], "rss": meta[0]["peak_rss_mb"], "cpus": meta[0]["allowed_cpus"]}


def determinism(name):
    p = ROOT / f"out/det/{name}.jsonl"
    if not p.exists():
        return None
    lines = [json.loads(l) for l in open(p)]
    if not any("meta" in l for l in lines):
        return None
    by = defaultdict(list)
    for l in lines:
        if "meta" not in l:
            by[l["clip"]].append((l["hyp"], json.dumps(l["words"])))
    same = sum(1 for v in by.values() if len(set(h for h, _ in v)) == 1)
    same_w = sum(1 for v in by.values() if len(set(v)) == 1)
    # cross-process: rep 0 of the det run vs the main correctness run (another process, other lane)
    main = {}
    for sub in ("all", "core", "mini", "turbo", "sil"):
        q = ROOT / f"out/{sub}/{name}.jsonl"
        if q.exists():
            for l in open(q):
                o = json.loads(l)
                if "meta" not in o:
                    main.setdefault(o["clip"], o["hyp"])
    both = [c for c in by if c in main]
    cross = sum(1 for c in both if by[c][0][0] == main[c])
    return same, same_w, len(by), cross, len(both)


def main():
    models = json.loads((ROOT / "models.json").read_text())
    rows = list(csv.DictReader(open(ROOT / "results.csv")))
    silby = defaultdict(list)
    for r in rows:
        if r["subset"] == "sil":
            silby[r["model"]].append(r)
    by = defaultdict(list)
    for r in rows:
        if r["subset"] in ("all", "core", "mini", "turbo"):
            by[r["model"]].append(r)
    core = set((ROOT / "corpus/subset_core.txt").read_text().split())
    summ = []
    for name, rs in by.items():
        if name not in models:
            continue
        subset = rs[0]["subset"]
        spec = models[name]
        full = [r for r in rs if r["type"] == "full"]
        tr = [r for r in rs if r["type"] == "trunc"]
        mid = [r for r in rs if r["type"] == "mid"]
        sil = [r for r in rs if r["type"] in ("silence", "noise")] + silby.get(name, [])
        pair = [r for r in rs if r["type"] == "pair"]
        short = [r for r in full if int(r["n"]) <= 2]
        mc = defaultdict(int)
        for r in mid:
            mc[r["mid_class"]] += 1
        tse = [abs(float(r["ts_err"])) for r in tr if r["ts_err"] not in ("", None)]
        tm = timing(name) or {}
        det = determinism(name)
        s = {"model": name, "subset": subset, "clips": len(rs), "family": spec["family"], "licence": spec["licence"],
             "size_mb": size_mb(spec),
             **{f"wer_{v}": wer([r for r in full if r["voice"] == v]) for v in VOICES},
             "trunc_n": len(tr),
             "trunc_exact": rate(tr, "exact")[0], "trunc_within1": rate(tr, "within1")[0],
             "trunc_exact_pos": rate(tr, "exact_pos")[0], "trunc_within1_pos": rate(tr, "within1_pos")[0],
             "trunc_under": rate(tr, "under")[0], "trunc_over": rate(tr, "over")[0],
             "tail_hall_trunc": rate(tr, "tail_hall")[0], "tail_hall_mid": rate(mid, "tail_hall")[0],
             "tail2_trunc": rate(tr, "tail_hall2")[0], "tail2_mid": rate(mid, "tail_hall2")[0],
             "junk_after_cut": sum(1 for r in tr if int(r["junk_tail"] or 0) > 0) / len(tr) if tr else None,
             "full_false_trunc": rate(full, "flagged")[0], "full_false_trunc_pos": rate(full, "flagged_pos")[0],
             "trunc_flagged": rate(tr, "flagged")[0], "trunc_flagged_pos": rate(tr, "flagged_pos")[0],
             "core_trunc_n": len([r for r in tr if r["clip"] in core]),
             "core_exact_sim": rate([r for r in tr if r["clip"] in core], "exact_sim")[0],
             "core_within1_sim": rate([r for r in tr if r["clip"] in core], "within1_sim")[0],
             "core_flagged_sim": rate([r for r in tr if r["clip"] in core], "flagged_sim")[0],
             "core_tail2": rate([r for r in tr + mid if r["clip"] in core], "tail_hall2")[0],
             "trunc_exact_sim": rate(tr, "exact_sim")[0], "trunc_within1_sim": rate(tr, "within1_sim")[0],
             "trunc_flagged_sim": rate(tr, "flagged_sim")[0], "full_false_trunc_sim": rate(full, "flagged_sim")[0],
             "clean_exact_sim": rate([r for r in tr if r["clean_cut"] == "1"], "exact_sim")[0],
             "unclean_exact_sim": rate([r for r in tr if r["clean_cut"] == "0"], "exact_sim")[0],
             "unclean_n": sum(1 for r in tr if r["clean_cut"] == "0"),
             "mid_completed": mc["completed"] / len(mid) if mid else None,
             "mid_guessed": mc["guessed"] / len(mid) if mid else None,
             "mid_dropped": mc["dropped"] / len(mid) if mid else None,
             "sil_halluc": f"{sum(int(r['nonempty']) for r in sil)}/{len(sil)}",
             "sil_examples": "; ".join(repr(r["hyp"])[:40] for r in sil if int(r["nonempty"])),
             "pair_both": rate(pair, "exact")[0], "pair_wer": wer(pair),
             "short_exact": rate(short, "exact")[0], "short_n": len(short),
             "ts_med_abs_err": st.median(tse) if tse else None,
             "rtf": tm.get("rtf"), "med_latency_s": tm.get("med_lat"), "short_latency_s": tm.get("short_lat"),
             "load_s": tm.get("load"), "peak_rss_mb": tm.get("rss"),
             "determinism": f"{det[0]}/{det[2]} text, {det[1]}/{det[2]} text+times x3; {det[3]}/{det[4]} vs main run" if det else None}
        summ.append(s)
    order = list(models)
    summ.sort(key=lambda s: order.index(s["model"]))
    with open(ROOT / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0]))
        w.writeheader()
        w.writerows(summ)
    f2 = lambda x, d=2: "-" if x is None else f"{x:.{d}f}"
    p = lambda x: "-" if x is None else f"{100 * x:.0f}%"
    L = ["### Headline (WER on all 336 full clips, except `turbo`-subset models: 60 full clips, see the same-clip table below; truncation with k̂_sim on the core trunc clips = 15 brief phrases x 4 voices, the same clips for every model except the models run on the `turbo` subset (fw-large-v3-turbo, moonv-*), whose trunc/mid clips are espeak175 only)", "",
         "| model | subset (clips) | size MB | licence | RTF 4 thr | median latency s (clips <1.2 s) | load s | peak RSS MB | WER 175 | WER 300 | WER 450 | WER piper | trunc exact | trunc within 1 | cut detected (trunc k̂<n) | false 'cut' on full | tail halluc trunc / mid (any hit > k+1) | tail completion trunc / mid (≥2 hits > k+1) | silence+noise non-empty | determinism |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summ:
        L.append(f"| {s['model']} | {s['subset']} ({s['clips']}) | {s['size_mb'] or '-'} | {s['licence']} | {f2(s['rtf'])} | "
                 f"{f2(s['med_latency_s'])} ({f2(s['short_latency_s'])}) | {f2(s['load_s'],1)} | {f2(s['peak_rss_mb'],0)} | "
                 + " | ".join(p(s[f'wer_{v}']) for v in VOICES) +
                 f" | {p(s['core_exact_sim'])} | {p(s['core_within1_sim'])} | {p(s['core_flagged_sim'])} | {p(s['full_false_trunc_sim'])} | "
                 f"{p(s['tail_hall_trunc'])} / {p(s['tail_hall_mid'])} | {p(s['tail2_trunc'])} / {p(s['tail2_mid'])} | {s['sil_halluc']} | {s['determinism'] or '-'} |")
    L += ["", "### Truncation detail over every trunc/mid clip the model ran (all k̂ variants), mid-word, pairs, short clips, timestamps", "",
          "| model | trunc clips | strict exact / w1 | lenient exact / w1 | sim exact / w1 | under / over (strict) | cut detected strict / lenient / sim | false 'cut' on full strict / lenient / sim | junk after cut | mid-word completed / guessed / dropped | pairs both heard | pair WER | short (n≤2) exact | last-word ts median abs err s | sim exact: clean / unclean espeak cuts |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summ:
        L.append(f"| {s['model']} | {s['trunc_n']} | {p(s['trunc_exact'])} / {p(s['trunc_within1'])} | {p(s['trunc_exact_pos'])} / {p(s['trunc_within1_pos'])} | "
                 f"{p(s['trunc_exact_sim'])} / {p(s['trunc_within1_sim'])} | {p(s['trunc_under'])} / {p(s['trunc_over'])} | "
                 f"{p(s['trunc_flagged'])} / {p(s['trunc_flagged_pos'])} / {p(s['trunc_flagged_sim'])} | "
                 f"{p(s['full_false_trunc'])} / {p(s['full_false_trunc_pos'])} / {p(s['full_false_trunc_sim'])} | {p(s['junk_after_cut'])} | "
                 f"{p(s['mid_completed'])} / {p(s['mid_guessed'])} / {p(s['mid_dropped'])} | {p(s['pair_both'])} | {p(s['pair_wer'])} | "
                 f"{p(s['short_exact'])} ({s['short_n']}) | {f2(s['ts_med_abs_err'],3)} | {p(s['clean_exact_sim'])} / {p(s['unclean_exact_sim'])} (n={s['unclean_n']}) |")
    # same-clip comparison on the turbo subset (all models ran these clips)
    tset = set((ROOT / "corpus/subset_turbo.txt").read_text().split())
    L += ["", "### Same 158 clips for every model (`turbo` subset: 15 brief phrases; full clips x 4 voices, trunc/mid at espeak175)", "",
          "| model | WER 175 | WER 300 | WER 450 | WER piper | trunc exact (175) | within 1 | false 'cut' on full (all 4 voices) | tail completion |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name in [s["model"] for s in summ]:
        rs = [r for r in by[name] if r["clip"] in tset]
        fu = [r for r in rs if r["type"] == "full"]
        tr = [r for r in rs if r["type"] == "trunc"]
        tm = [r for r in rs if r["type"] in ("trunc", "mid")]
        L.append(f"| {name} | " + " | ".join(p(wer([r for r in fu if r['voice'] == v])) for v in VOICES) +
                 f" | {p(rate(tr,'exact_sim')[0])} | {p(rate(tr,'within1_sim')[0])} | {p(rate(fu,'flagged_sim')[0])} | {p(rate(tm,'tail_hall2')[0])} |")
    # per voice
    L += ["", "### Per voice (k̂_sim). len ratio = median normalised hyp tokens / ref tokens on full clips", "",
          "| model | voice | WER | len ratio | trunc exact | within 1 | cut detected | false 'cut' on full | tail halluc trunc+mid |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name in [s["model"] for s in summ]:
        rs = by[name]
        for v in VOICES:
            fu = [r for r in rs if r["voice"] == v and r["type"] == "full"]
            tr = [r for r in rs if r["voice"] == v and r["type"] == "trunc"]
            tm = [r for r in rs if r["voice"] == v and r["type"] in ("trunc", "mid")]
            lr = [int(r["hyp_len"] or 0) / int(r["n"]) for r in fu if r.get("hyp_len") not in ("", None)]
            L.append(f"| {name} | {v} | {p(wer(fu))} | {f2(st.median(lr)) if lr else '-'} | {p(rate(tr,'exact_sim')[0])} | {p(rate(tr,'within1_sim')[0])} | "
                     f"{p(rate(tr,'flagged_sim')[0])} | {p(rate(fu,'flagged_sim')[0])} | {p(rate(tm,'tail_hall')[0])} |")
    (ROOT / "tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
