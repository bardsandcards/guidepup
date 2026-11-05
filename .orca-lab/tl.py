#!/usr/bin/env python3
"""Prints a lab timeline per test: speak/cut/end events with timings (ms from test start)."""
import json, sys
path = sys.argv[1]; only = sys.argv[2] if len(sys.argv) > 2 else None
t0 = None; cur = None; speaks = {}
for line in open(path):
    e = json.loads(line)
    if e["ev"] == "test":
        cur = e["name"]; t0 = e["wall"]
        if not only or cur == only: print(f"--- {cur}")
        continue
    if e["ev"] == "test-end":
        cur = None; continue
    if cur is None or (only and cur != only):
        continue
    rel = e["wall"] - t0
    if e["ev"] == "speak":
        speaks[e["id"]] = e
        print(f"{rel:7.0f} SPEAK#{e['id']} [{e['kind']}] {e['text']!r} ({e['durMs']:.0f}ms)")
    elif e["ev"] == "end":
        print(f"{rel:7.0f}   END#{e['id']} (heard in full)")
    elif e["ev"] == "cut":
        print(f"{rel:7.0f}   CUT#{e['id']} after {e['heardMs']:.0f}/{e['durMs']:.0f}ms heard={e['heardText']!r} partial={e['partialWord']!r}")
