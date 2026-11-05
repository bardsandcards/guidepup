#!/usr/bin/env python3
"""Estimates what was heard from Orca's own test log alone (no timed module):
replays timestamped speech + interrupt records through a model of speechd's
queue (MESSAGE never interrupts MESSAGE; Orca's cancel cuts the current
utterance and drops the queue), with utterance durations from libespeak-ng.
Compares with the timed module's ground truth when the run has one.

    estimate.py <out/label> [--rate N] [--duration espeak|chars]

Run inside guidepup-orca:26.04-audio (needs libespeak-ng).
"""
import argparse
import ctypes
import json
import os
import re
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--rate", type=int, default=None, help="speechd rate; default: from the run's guidepup.ini")
ap.add_argument("--duration", choices=["espeak", "chars"], default="espeak")
args = ap.parse_args()

# --- durations -------------------------------------------------------------

class EspeakEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("unique_identifier", ctypes.c_uint), ("text_position", ctypes.c_int),
                ("length", ctypes.c_int), ("audio_position", ctypes.c_int), ("sample", ctypes.c_int),
                ("user_data", ctypes.c_void_p), ("id", ctypes.c_char * 8)]


SYNTH_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.POINTER(EspeakEvent))
espeak = ctypes.CDLL("libespeak-ng.so.1")
SR = espeak.espeak_Initialize(2, 0, None, 0)
espeak.espeak_SetVoiceByName(b"en-us")
_n = [0]
_words = []


@SYNTH_CB
def _cb(wav, n, events):
    _n[0] += max(n, 0)
    i = 0
    while events[i].type != 0:
        if events[i].type == 1:
            _words.append((events[i].audio_position, events[i].text_position, events[i].length))
        i += 1
    return 0


espeak.espeak_SetSynthCallback(_cb)


def wpm_for(rate):
    return 170 + (170 - 80) * rate // 100 if rate < 0 else 170 + (449 - 170) * rate // 100


def synth(text):
    _n[0] = 0
    _words.clear()
    raw = text.encode() + b"\0"
    espeak.espeak_Synth(raw, len(raw), 0, 1, 0, 1, None, None)
    chars = list(text)
    words = [(a, "".join(chars[p - 1:p - 1 + l])) for a, p, l in _words]
    return _n[0] / SR * 1000, words


def chars_duration(text, wpm):
    # ~18.5 chars/s at 170 wpm (fitted on espeak-ng en-us), scaled linearly with rate.
    return len(text) / (18.5 * wpm / 170) * 1000


rate = args.rate
if rate is None:
    ini = open(f"{args.run}/guidepup.ini").read()
    m = re.search(r"\[voice-sets/primary/default\][^\[]*?rate=(\d+)", ini)
    rate = int(m.group(1)) * 2 - 100 if m else 0
wpm = wpm_for(rate)
espeak.espeak_SetParameter(1, wpm, 0)


def heard_words(words, dur, elapsed):
    full = []
    for i, (start, w) in enumerate(words):
        end = words[i + 1][0] if i + 1 < len(words) else dur
        if end <= elapsed:
            full.append(w)
        else:
            break
    return " ".join(full)


# --- model -----------------------------------------------------------------

def simulate(records):
    """records: [(wall, 'speech', text) | (wall, 'interrupt', None)] → per-utterance outcome."""
    out = []
    playing = None  # dict(start, dur, idx)
    queue = []

    def advance(t):
        nonlocal playing
        while playing and playing["start"] + playing["dur"] <= t:
            out[playing["idx"]]["outcome"] = "full"
            end = playing["start"] + playing["dur"]
            playing = None
            if queue:
                nxt = queue.pop(0)
                nxt["start"] = end
                playing = nxt

    for wall, kind, text in records:
        advance(wall)
        if kind == "speech":
            dur, words = synth(text) if args.duration == "espeak" else (chars_duration(text, wpm), [])
            out.append({"text": text, "dur": dur, "words": words, "outcome": "pending"})
            u = {"start": wall, "dur": dur, "idx": len(out) - 1}
            if playing is None:
                playing = u
            else:
                queue.append(u)
        else:
            if playing:
                el = wall - playing["start"]
                o = out[playing["idx"]]
                o.update(outcome="cut", heardMs=el, heardText=heard_words(o["words"], o["dur"], el))
                playing = None
            for q in queue:
                out[q["idx"]]["outcome"] = "dropped"
            queue.clear()
    advance(float("inf"))
    return out


# --- ground truth from the timed module -------------------------------------

def truth_by_test(run):
    path = f"{run}/timeline.jsonl"
    if not os.path.exists(path):
        return {}
    res = defaultdict(list)
    cur = None
    for line in open(path):
        e = json.loads(line)
        if e["ev"] == "test":
            cur = e["name"]
        elif e["ev"] == "test-end":
            cur = None
        elif cur and e["ev"] == "speak" and e["kind"] == "SPEAK":
            res[cur].append({"id": e["id"], "text": e["text"], "outcome": "pending"})
        elif cur and e["ev"] in ("end", "cut"):
            for u in res[cur]:
                if u["id"] == e["id"]:
                    u["outcome"] = "full" if e["ev"] == "end" else "cut"
                    if e["ev"] == "cut":
                        u["heardMs"], u["heardText"] = e["heardMs"], e["heardText"]
    return res


truth = truth_by_test(args.run)
summary = defaultdict(int)
for name in sorted(d for d in os.listdir(args.run) if os.path.exists(f"{args.run}/{d}/orca-timed.jsonl")):
    p = f"{args.run}/{name}/orca-timed.jsonl"
    if not os.path.exists(p):
        continue
    recs = [json.loads(l) for l in open(p)]
    records = [(r["wall"], "interrupt" if r["kind"] == "interrupt" else "speech", r.get("text"))
               for r in recs if r["log"] == "speech"]
    est = simulate(records)
    tru = [u for u in truth.get(name, [])]
    print(f"=== {name}")
    for i, e in enumerate(est):
        t = tru[i] if i < len(tru) and tru[i]["text"].strip() == e["text"].strip() else None
        es = e["outcome"] + (f" @{e['heardMs']:.0f}ms {e['heardText']!r}" if e["outcome"] == "cut" else "")
        ts = "-" if t is None else t["outcome"] + (f" @{t['heardMs']:.0f}ms {t['heardText']!r}" if t["outcome"] == "cut" else "")
        ok = t is not None and t["outcome"] == e["outcome"] and (e["outcome"] != "cut" or t["heardText"] == e["heardText"])
        summary["utterances"] += 1
        if t is not None:
            summary["compared"] += 1
            summary["outcome_match"] += t["outcome"] == e["outcome"]
            summary["exact_match"] += ok
            if e["outcome"] == "cut" and t["outcome"] == "cut":
                summary["cut_pairs"] += 1
                summary["abs_ms_err_sum"] += abs(e["heardMs"] - t["heardMs"])
        print(f"  {'OK ' if ok else '   '}{e['text'][:44]!r:48} est={es:42} truth={ts}")
print("SUMMARY", json.dumps({**summary, "rate": rate, "wpm": wpm, "duration": args.duration,
                             "mean_cut_ms_err": round(summary["abs_ms_err_sum"] / summary["cut_pairs"], 1) if summary["cut_pairs"] else None}))
