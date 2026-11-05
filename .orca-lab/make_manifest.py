#!/usr/bin/env python3
"""Builds an ASR manifest from timed-module runs with CLIPS=1: one row per played clip.

    make_manifest.py <out/label>... > manifest.jsonl
Rows: clip (absolute host path), text (what Orca sent), outcome (full|cut), heardText (whole words played),
partialWord, heardMs, durMs, rate (wpm), test.
"""
import json, os, sys
for run in sys.argv[1:]:
    run = os.path.abspath(run)
    cur, wpm, speaks = None, None, {}
    for line in open(f"{run}/timeline.jsonl"):
        e = json.loads(line)
        if e["ev"] == "test":
            cur = e["name"]
        elif e["ev"] == "rate":
            wpm = e["wpm"]
        elif e["ev"] == "speak":
            speaks[e["id"]] = (e, wpm)
        elif e["ev"] in ("end", "cut") and e.get("clip") and e["id"] in speaks:
            s, w = speaks[e["id"]]
            clip = e["clip"].replace("/work/", os.path.dirname(os.path.dirname(os.path.dirname(run))) + "/", 1)
            print(json.dumps({"clip": clip, "text": s["text"], "kind": s["kind"],
                              "outcome": "full" if e["ev"] == "end" else "cut",
                              "heardText": s["text"] if e["ev"] == "end" else e["heardText"],
                              "partialWord": None if e["ev"] == "end" else e["partialWord"],
                              "heardMs": e.get("heardMs", s["durMs"]), "durMs": s["durMs"], "wpm": w,
                              "test": cur, "run": os.path.basename(run)}))
