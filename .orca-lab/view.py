#!/usr/bin/env python3
"""Merged per-test view of a lab run: what guidepup got, what Orca logged, what was
heard (timed module), and what the braille display showed (vr driver).

    view.py <out/label> [test-slug]
"""
import json
import os
import sys

run = sys.argv[1]
only = sys.argv[2] if len(sys.argv) > 2 else None


def load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


timeline = load(f"{run}/timeline.jsonl")
vr = load(f"{run}/vr.jsonl")
tests = []
for e in timeline:
    if e["ev"] == "test":
        tests.append([e["name"], e["wall"], None])
    elif e["ev"] == "test-end" and tests:
        tests[-1][2] = e["wall"]

for name, t0, t1 in tests:
    if only and name != only:
        continue
    t1 = t1 or float("inf")
    rows = []
    for e in timeline:
        if not (t0 <= e["wall"] <= t1):
            continue
        if e["ev"] == "speak":
            rows.append((e["wall"], "speech", f"SPEAK#{e['id']} {e['text']!r} ({e['durMs']:.0f}ms)"))
        elif e["ev"] == "end":
            rows.append((e["wall"], "speech", f"  END#{e['id']} heard in full"))
        elif e["ev"] == "cut":
            rows.append((e["wall"], "speech", f"  CUT#{e['id']} at {e['heardMs']:.0f}/{e['durMs']:.0f}ms heard={e['heardText']!r}+{e['partialWord']!r}"))
    for e in load(f"{run}/{name}/orca-timed.jsonl"):
        if e["log"] == "speech":
            if e["kind"] == "interrupt":
                rows.append((e["wall"], "orca", "interrupt"))
            else:
                rows.append((e["wall"], "orca", f"speech {e['text']!r}"))
        elif e["log"] == "braille":
            rows.append((e["wall"], "orca-brl", f"{e['visible']!r}"))
    for e in vr:
        if t0 <= e["wall"] <= t1 and e["ev"] == "visual":
            rows.append((e["wall"], "display", f"{e['text'].rstrip()!r}"))
    print(f"=== {name}")
    for wall, chan, text in sorted(rows, key=lambda r: r[0]):
        print(f"{wall - t0:7.0f}  {chan:9} {text}")
