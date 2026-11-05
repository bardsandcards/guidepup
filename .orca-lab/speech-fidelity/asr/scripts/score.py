"""Score model outputs against the clip manifest.

usage: venvs/align/bin/python scripts/score.py out/<subset>/<name>.jsonl [...]
Writes results.csv (one row per model x clip; appends/replaces rows for the given models) and
prints nothing else. summarize.py builds the tables.

Alignment: Levenshtein between normalised hypothesis tokens and the FULL normalised reference
(sub = ins = del = 1). Backtrace from the end preferring "reference token deleted" on ties, so
repeated words ("testing testing", "button button") align as early as possible (the
conservative choice for tail hallucination).

  k_hat     = 1 + index of the last reference token aligned as an exact hit (0 if none)
  exact     = k_hat == k ; within1 = |k_hat - k| <= 1 ; under = k_hat < k ; over = k_hat > k
  tail_hall = any exact hit at reference position > k+1 (1-based), i.e. beyond the word right
              after the cut: the model "completed" the sentence
  tail_hall2 = stricter: at least 2 exact hits beyond k+1 (a single shared function word in
              unrelated junk, e.g. "I'll see you next time" hitting "will", is not completion)
  junk_tail = hypothesis tokens after the last hit that are not hits (inserted / substituted)
  flagged   = k_hat < n (a checker comparing against the known text would say "cut off")
  k_pos     = lenient variant: 1 + last reference position aligned to ANY hypothesis token (hit or
              substitution), i.e. "how far into the known text the model got" even when it
              misheard words; exact_pos / within1_pos / flagged_pos likewise. Because sub = ins,
              any junk after the last hit aligns as substitutions of the next reference tokens,
              so this variant counts junk tails as progress.
  k_sim     = middle variant (the headline one): like k_pos but a substitution counts only if the
              two tokens are character-similar (difflib ratio >= 0.5: "card"/"cart" counts,
              "video"/"42.50" does not)
  mid-word clips (k full tokens + half of token k+1):
      mid_class = completed (token k+1 hit) | guessed (some non-hit token after token k's
      position) | dropped (nothing after) ; tail_hall there = hit beyond k+1
"""
import csv, json, sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from textnorm import norm  # noqa

FIELDS = ["model", "subset", "clip", "voice", "type", "pid", "n", "k", "dur", "cut", "ref", "hyp",
          "hyp_norm", "edits", "ref_len", "k_hat", "exact", "within1", "under", "over", "tail_hall",
          "tail_hall2", "junk_tail", "flagged", "k_pos", "exact_pos", "within1_pos", "flagged_pos",
          "k_sim", "exact_sim", "within1_sim", "flagged_sim", "hyp_len", "mid_class", "nonempty", "has_words", "last_word_end",
          "ts_err", "clean_cut", "t", "error"]


def align(hyp, ref):
    """Return list of ops (op, hyp_idx, ref_idx) with op in hit/sub/ins/del."""
    H, R = len(hyp), len(ref)
    D = [[0] * (R + 1) for _ in range(H + 1)]
    for i in range(H + 1):
        D[i][0] = i
    for j in range(R + 1):
        D[0][j] = j
    for i in range(1, H + 1):
        for j in range(1, R + 1):
            c = 0 if hyp[i - 1] == ref[j - 1] else 1
            D[i][j] = min(D[i - 1][j - 1] + c, D[i - 1][j] + 1, D[i][j - 1] + 1)
    ops, i, j = [], H, R
    while i > 0 or j > 0:
        if j > 0 and D[i][j] == D[i][j - 1] + 1:
            ops.append(("del", None, j - 1)); j -= 1
        elif i > 0 and j > 0 and D[i][j] == D[i - 1][j - 1] + (0 if hyp[i - 1] == ref[j - 1] else 1):
            ops.append(("hit" if hyp[i - 1] == ref[j - 1] else "sub", i - 1, j - 1)); i -= 1; j -= 1
        else:
            ops.append(("ins", i - 1, None)); i -= 1
    return ops[::-1], D[H][R]


def score_clip(clip, out):
    ref = clip["ref"]
    hyp = norm(out.get("hyp", ""))
    row = {"clip": clip["clip"], "voice": clip["voice"], "type": clip["type"], "pid": clip["pid"],
           "n": clip["n"], "k": clip["k"], "dur": clip["dur"], "cut": clip.get("cut"),
           "ref": " ".join(ref), "hyp": out.get("hyp", ""), "hyp_norm": " ".join(hyp),
           "nonempty": int(bool(hyp)), "t": out.get("t"), "error": out.get("error", "")}
    words = out.get("words") or []
    row["has_words"] = int(bool(words) and words[-1][2] is not None)
    row["last_word_end"] = words[-1][2] if row["has_words"] else ""
    if not ref:
        return row
    t = clip["type"]
    tref = ref if t != "full" else ref
    ops, _ = align(hyp, tref)
    hits = [(hi, ri) for op, hi, ri in ops if op == "hit"]
    k_hat = (hits[-1][1] + 1) if hits else 0
    hs = [ri for op, hi, ri in ops if op in ("hit", "sub")]
    k_pos = (hs[-1] + 1) if hs else 0
    sim = [ri for op, hi, ri in ops if op == "hit" or (op == "sub" and SequenceMatcher(None, hyp[hi], ref[ri]).ratio() >= 0.5)]
    k_sim = (sim[-1] + 1) if sim else 0
    last_hit_h = hits[-1][0] if hits else -1
    junk = sum(1 for op, hi, ri in ops if hi is not None and hi > last_hit_h and op != "hit")
    k, n = clip["k"], clip["n"]
    row.update(k_hat=k_hat, junk_tail=junk, flagged=int(k_hat < n), k_pos=k_pos, flagged_pos=int(k_pos < n),
               k_sim=k_sim, flagged_sim=int(k_sim < n), hyp_len=len(hyp))
    kk = n if t == "full" else k
    if t in ("full", "trunc", "mid"):
        row.update(exact_pos=int(k_pos == kk), within1_pos=int(abs(k_pos - kk) <= 1),
                   exact_sim=int(k_sim == kk), within1_sim=int(abs(k_sim - kk) <= 1))
    if t == "full":
        _, e = align(hyp, ref)
        row.update(edits=e, ref_len=len(ref), exact=int(k_hat == n), within1=int(abs(k_hat - n) <= 1),
                   under=int(k_hat < n), over=0, tail_hall=0)
        if row["has_words"] and clip.get("tok_end"):
            row["ts_err"] = round(words[-1][2] - clip["tok_end"][str(n)], 3)
    elif t in ("trunc", "mid"):
        _, e = align(hyp, ref[:k])
        beyond = [ri for _, ri in hits if ri + 1 > k + 1]
        tail = int(bool(beyond))
        row["tail_hall2"] = int(len(beyond) >= 2)
        row.update(edits=e, ref_len=k, exact=int(k_hat == k), within1=int(abs(k_hat - k) <= 1),
                   under=int(k_hat < k), over=int(k_hat > k), tail_hall=tail)
        if t == "mid":
            if any(ri == k for _, ri in hits):
                mc = "completed"
            else:
                # hypothesis position of the hit on token k (1-based), else the last hit before it
                prev = [hi for hi, ri in hits if ri <= k - 1]
                base = prev[-1] if prev else -1
                mc = "guessed" if len(hyp) - 1 > base else "dropped"
            row["mid_class"] = mc
        if row["has_words"] and t == "trunc" and clip.get("word_end") is not None:
            # last emitted word's end vs the audio cut (word k's aligned end = clip["word_end"])
            row["ts_err"] = round(words[-1][2] - clip["word_end"], 3)
    elif t == "pair":
        _, e = align(hyp, ref)
        ka = clip["k"]
        first = any(ri < ka for _, ri in hits)
        second = any(ri >= ka for _, ri in hits)
        row.update(edits=e, ref_len=len(ref), exact=int(first and second), within1="", under="", over="",
                   tail_hall="")
    return row


def main(paths):
    clips = {}
    for mf in ("corpus/clips.jsonl", "corpus/clips_sil.jsonl", "corpus/clips_real.jsonl"):
        if (ROOT / mf).exists():
            clips.update({json.loads(l)["clip"]: json.loads(l) for l in open(ROOT / mf)})
    # espeak trunc clips whose cut is at most 20 ms past espeak's own next-word start event
    evp = ROOT / "corpus/event_check.json"
    clean = {e["clip"]: int(e["cut_minus_ev"] <= 0.020) for e in json.loads(evp.read_text())} if evp.exists() else {}
    new = []
    for p in paths:
        p = Path(p)
        subset = p.parent.name
        name = p.stem
        lines = [json.loads(l) for l in open(p)]
        meta = [l["meta"] for l in lines if "meta" in l]
        if not meta:
            print(f"skip {p}: no meta (incomplete)", file=sys.stderr)
            continue
        for o in lines:
            if "meta" in o or o.get("rep", 0) != 0:
                continue
            r = score_clip(clips[o["clip"]], o)
            r.update(model=name, subset=subset, clean_cut=clean.get(o["clip"], ""))
            new.append(r)
    out = ROOT / "results.csv"
    keep = []
    names = {(r["model"], r["subset"]) for r in new}
    if out.exists():
        with open(out) as f:
            keep = [r for r in csv.DictReader(f) if (r["model"], r["subset"]) not in names]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in keep + new:
            w.writerow(r)
    print(f"results.csv: {len(keep)} kept + {len(new)} new rows", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
