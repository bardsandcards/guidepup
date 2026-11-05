#!/usr/bin/env python3
"""Compares the sounding length of real sd_espeak-ng recordings with the lab module's
libespeak-ng synthesis of the same text (first to last loud 10 ms frame, both sides)."""
import array
import ctypes
import sys
import wave


def loud_extent(samples, sr, thr=300):
    f = sr // 100
    frames = [max((abs(x) for x in samples[i * f:(i + 1) * f]), default=0) > thr for i in range(len(samples) // f)]
    idx = [i for i, v in enumerate(frames) if v]
    return 0 if not idx else (idx[-1] - idx[0] + 1) * 10


SYNTH_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
espeak = ctypes.CDLL("libespeak-ng.so.1")
SR = espeak.espeak_Initialize(2, 0, None, 0)
espeak.espeak_SetVoiceByName(b"en-us")
buf = array.array("h")


@SYNTH_CB
def cb(wav, n, events):
    if n > 0:
        buf.frombytes(ctypes.string_at(wav, n * 2))
    return 0


espeak.espeak_SetSynthCallback(cb)
print(f"{'rate':>4} {'real ms':>8} {'module ms':>9} {'diff%':>6}  text")
for line in open(sys.argv[1]):
    rate, path, text = line.rstrip("\n").split("\t")
    rate = int(rate)
    w = wave.open(path)
    real = loud_extent(array.array("h", w.readframes(w.getnframes())), w.getframerate())
    wpm = 170 + (449 - 170) * rate // 100 if rate >= 0 else 170 + 90 * rate // 100
    espeak.espeak_SetParameter(1, wpm, 0)
    del buf[:]
    raw = text.encode() + b"\0"
    espeak.espeak_Synth(raw, len(raw), 0, 1, 0, 1, None, None)
    mod = loud_extent(buf, SR)
    print(f"{rate:>4} {real:>8} {mod:>9} {100 * (mod - real) / real if real else float('nan'):>6.1f}  {text[:60]}")
