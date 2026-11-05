#!/usr/bin/env python3
"""A virtual braille display for BRLTTY's Virtual (vr) driver, logging what it shows.

    vr-display.py <socket> <cells> <out.jsonl>

BRLTTY connects as the client (`-b vr -d client:<socket>`). We announce the
display size with `cells`, then log each `Visual` (text window) and `Braille`
(dot patterns) line with a wall-clock timestamp, as Unicode braille plus a
back-translation of the dots with liblouis (en-us-g2, uncontracted fallback).
"""
import json
import os
import socket
import sys
import time

try:
    import louis
except ImportError:  # pragma: no cover
    louis = None

path, cells, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]


def unescape(s):
    result, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n in "Xx":
                j = i + 2
                while j < len(s) and s[j] in "0123456789abcdefABCDEF":
                    j += 1
                result.append(chr(int(s[i + 2 : j], 16)))
                i = j
                continue
            result.append(n)
            i += 2
            continue
        result.append(c)
        i += 1
    return "".join(result)


def dots_to_unicode(field):
    """`Braille` strings are cells separated by `|`, each a run of dot numbers."""
    out_cells = []
    for cell in field.split("|"):
        bits = 0
        for d in cell:
            if d.isdigit() and d != "0":
                bits |= 1 << (int(d) - 1)
        out_cells.append(chr(0x2800 + bits))
    return "".join(out_cells)


def back_translate(unicode_braille):
    if louis is None:
        return None
    # Dots 7-8 mark the cursor and (in computer braille) capitals; 6-dot tables don't know them.
    unicode_braille = "".join(chr(0x2800 | ((ord(c) - 0x2800) & 0x3F)) for c in unicode_braille)
    try:
        return {
            t: louis.backTranslateString([f"en-ueb-g{g}.ctb"], unicode_braille, mode=louis.dotsIO | louis.ucBrl)
            for g, t in ((2, "ueb_g2"), (1, "ueb_g1"))
        }
    except Exception as e:  # liblouis errors are informative, keep them
        return {"error": str(e)}


if os.path.exists(path):
    os.unlink(path)
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(path)
server.listen(1)
log = open(out, "a", buffering=1, encoding="utf-8")


def record(**fields):
    log.write(json.dumps({"wall": round(time.time() * 1000), **fields}, ensure_ascii=False) + "\n")


while True:
    conn, _ = server.accept()
    record(ev="connected")
    conn.sendall(f"cells {cells}\n".encode())
    buf = b""
    while True:
        data = conn.recv(4096)
        if not data:
            record(ev="disconnected")
            break
        buf += data
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            line = raw.decode("utf-8", "replace").rstrip("\r")
            word, _, rest = line.partition(" ")
            if rest.startswith('"') and rest.endswith('"'):
                value = unescape(rest[1:-1])
            else:
                value = rest
            if word == "Visual":
                record(ev="visual", text=value)
            elif word == "Braille":
                uni = dots_to_unicode(value)
                record(ev="braille", dots=value, unicode=uni, back=back_translate(uni))
            else:
                record(ev=word.lower() or "line", value=value)
