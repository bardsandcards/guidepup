"""Shared harness for every model runner.

A runner module calls run(load_fn, family) where load_fn(model, threads) returns
transcribe(x: np.float32 16 kHz mono) -> (text, words) with words = [[w, start_s, end_s], ...]
or None when the backend has no word timestamps.

Writes one JSON line per clip ({"clip","hyp","words","t"}) and a final {"meta": ...} line:
load time, peak RSS, threads' allowed CPUs (affinity audit), argv.
"""
import argparse, json, os, resource, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / "models/hf"))


def allowed_cpus():
    seen = set()
    for t in Path("/proc/self/task").iterdir():
        try:
            for line in (t / "status").read_text().splitlines():
                if line.startswith("Cpus_allowed_list"):
                    seen.add(line.split()[1])
        except OSError:
            pass
    return sorted(seen)


def subset_ids(name):
    if name in ("all", "sil", "real"):
        return None
    p = ROOT / f"corpus/subset_{name}.txt"
    return set(p.read_text().split())


def run(load_fn, family):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--subset", default="all")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--manifest", default="corpus/clips.jsonl")
    a = ap.parse_args()
    import soundfile as sf

    if a.subset in ("sil", "real"):
        a.manifest = f"corpus/clips_{a.subset}.jsonl"
    rows = [json.loads(l) for l in open(ROOT / a.manifest)]
    ids = subset_ids(a.subset)
    if ids is not None:
        rows = [r for r in rows if r["clip"] in ids]
    t0 = time.perf_counter()
    transcribe = load_fn(a.model, a.threads)
    t_load = time.perf_counter() - t0
    import numpy as np
    rng = np.random.default_rng(0)
    transcribe((rng.standard_normal(16000) * 1e-4).astype("float32"))  # warm-up, discarded
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    errors = 0
    with open(out, "w") as f:
        for rep in range(a.repeat):
            for r in rows:
                x, sr = sf.read(str(ROOT / "corpus/clips" / f"{r['clip']}.wav"), dtype="float32")
                assert sr == 16000
                t1 = time.perf_counter()
                try:
                    text, words = transcribe(x)
                    err = None
                except Exception as e:  # keep going, record it
                    text, words, err = "", None, repr(e)[:300]
                    errors += 1
                dt = time.perf_counter() - t1
                rec = {"clip": r["clip"], "rep": rep, "hyp": text, "words": words, "t": round(dt, 4), "dur": r["dur"]}
                if err:
                    rec["error"] = err
                f.write(json.dumps(rec) + "\n")
                f.flush()
        meta = {"family": family, "model": a.model, "subset": a.subset, "threads": a.threads,
                "n_clips": len(rows), "repeat": a.repeat, "load_s": round(t_load, 3),
                "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
                "allowed_cpus": allowed_cpus(), "errors": errors,
                "sched_affinity": sorted(os.sched_getaffinity(0)), "argv": sys.argv}
        f.write(json.dumps({"meta": meta}) + "\n")
    print(json.dumps(meta), flush=True)
