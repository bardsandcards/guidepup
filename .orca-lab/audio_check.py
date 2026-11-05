#!/usr/bin/env python3
"""Checks the timed module's "heard" numbers against the recorded audio (MODE=audio).

For each utterance, measures how long the null sink's monitor carried sound
between its BEGIN and its END/CUT, and compares with the module's own figure.
Also writes per-utterance WAV clips + a manifest for ASR (clips/<test>/<id>.wav).

    audio_check.py <out/label>
"""
import array
import json
import os
import sys
import wave

run = sys.argv[1]
wav = wave.open(f"{run}/session.wav")
sr = wav.getframerate()
assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
pcm = array.array("h", wav.readframes(wav.getnframes()))
start_wall = int(open(f"{run}/session.wav.start").read())
FRAME = int(sr * 0.01)  # 10 ms


def energy(i):
    seg = pcm[i * FRAME:(i + 1) * FRAME]
    return max((abs(x) for x in seg), default=0)


frames = len(pcm) // FRAME
loud = [energy(i) > 300 for i in range(frames)]


def active_ms(t_from, t_to):
    """Last 10 ms frame with sound in [t_from, t_to), relative to t_from (ms)."""
    a = max(0, int((t_from - start_wall) / 10))
    b = min(frames, int((t_to - start_wall) / 10) + 1)
    last = None
    first = None
    for i in range(a, b):
        if loud[i]:
            first = i if first is None else first
            last = i
    if last is None:
        return None, None
    return (first - a) * 10, (last - a + 1) * 10


events = [json.loads(l) for l in open(f"{run}/timeline.jsonl")]

# The recording lags the module's clock (pacat + null sink + parecord buffering).
# Estimate the lag from utterances that begin after >=400 ms of module silence.
def estimate_offset():
    lags, last_stop = [], None
    for e in events:
        if e["ev"] == "begin":
            if last_stop is not None and e["wall"] - last_stop >= 400:
                a = max(0, int((e["wall"] - start_wall) / 10))
                for i in range(a, min(frames, a + 60)):  # look 0-600 ms ahead
                    if loud[i] and not any(loud[max(0, i - 30):i]):
                        lags.append((i - a) * 10)
                        break
        elif e["ev"] in ("end", "cut"):
            last_stop = e["wall"]
    lags.sort()
    return (lags[len(lags) // 2] if lags else 0), len(lags)


OFFSET, n_off = estimate_offset()
print(f"recording lag ~{OFFSET} ms (median of {n_off} onsets after silence)")
start_wall -= OFFSET
os.makedirs(f"{run}/clips", exist_ok=True)
manifest = open(f"{run}/clips/manifest.jsonl", "w")
cur = None
utts = {}
rows = []
for e in events:
    if e["ev"] == "test":
        cur = e["name"]
    elif e["ev"] == "speak":
        utts[e["id"]] = {"test": cur, "text": e["text"], "kind": e["kind"], "durMs": e["durMs"], "words": e["words"]}
    elif e["ev"] == "begin" and e["id"] in utts:
        utts[e["id"]]["begin"] = e["wall"]
    elif e["ev"] in ("end", "cut") and e["id"] in utts:
        u = utts[e["id"]]
        u["stop"] = e["wall"]
        u["module_heard"] = e.get("heardMs", u["durMs"])
        u["outcome"] = "full" if e["ev"] == "end" else "cut"
        u["heardText"] = e.get("heardText", u["text"])
        if "begin" not in u:
            continue
        # look a little past the stop for buffered audio still draining
        onset, off = active_ms(u["begin"], u["stop"] + 30)
        u["audio_onset"], u["audio_heard"] = onset, off
        rows.append(u)
        if u["test"] and onset is not None:
            d = f"{run}/clips/{u['test']}"
            os.makedirs(d, exist_ok=True)
            a = max(0, int((u["begin"] - start_wall) * sr / 1000))
            b = min(len(pcm), int((u["stop"] + 30 - start_wall) * sr / 1000))
            path = f"{d}/{e['id']}.wav"
            w = wave.open(path, "w")
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(pcm[a:b].tobytes()); w.close()
            manifest.write(json.dumps({"clip": os.path.relpath(path, run), "test": u["test"], "text": u["text"],
                                       "outcome": u["outcome"], "heardText": u["heardText"],
                                       "moduleHeardMs": u["module_heard"], "audioHeardMs": off,
                                       "durMs": u["durMs"], "words": u["words"]}) + "\n")

errs = []
for u in rows:
    if u.get("test") is None:
        continue
    diff = None if u["audio_heard"] is None else u["audio_heard"] - u["module_heard"]
    if diff is not None:
        errs.append(diff)
    print(f"{u['test']:8} {u['outcome']:4} module={u['module_heard']:7.0f}ms audio={u['audio_heard']}ms "
          f"onset={u['audio_onset']}ms diff={diff} {u['text'][:50]!r}")
if errs:
    errs.sort()
    print("SUMMARY", json.dumps({"n": len(errs), "median_diff_ms": errs[len(errs) // 2],
                                 "min": errs[0], "max": errs[-1]}))
