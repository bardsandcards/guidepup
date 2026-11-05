#!/usr/bin/env python3
"""Lab speech-dispatcher output module for guidepup: speech that takes real time.

Drop-in for the asset's `speechd/modules/guidepup`. It keeps guidepup's socket
protocol ({"type": "ready" | "speech" | "stop" | "cancel"} JSONL) and adds:

- GP_SPEECH_MODE=instant  BEGIN+END straight away (the asset's behaviour)
                 timed    synthesise with libespeak-ng, hold END for the audio's length
                 audio    as timed, and play the audio through `pacat` (PulseAudio)
- On STOP while speaking: a {"type": "cut"} message and timeline record giving
  how much of the utterance had played, by word (espeak-ng WORD events).
- GP_TIMELINE=<file>: JSONL timeline of every protocol event, for the lab.
"""

import ctypes
import html
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import wave

MODE = os.environ.get("GP_SPEECH_MODE", "timed")
TIMELINE = os.environ.get("GP_TIMELINE")
SOCKET_PATH = os.environ["GUIDEPUP_ORCA_SPEECH_SOCKET"]
PULSE_LATENCY_MS = int(os.environ.get("GP_PULSE_LATENCY_MS", "30"))
CLIPS = os.environ.get("GP_CLIPS_DIR")  # save what played of each utterance as WAV

# sd_espeak-ng's defaults (espeak-ng.conf) and speechd's -100..100 rate scale.
ESPEAK_MIN_RATE, ESPEAK_NORMAL_RATE, ESPEAK_MAX_RATE = 80, 170, 449

T0 = time.monotonic()
out_lock = threading.Lock()
timeline_lock = threading.Lock()


def now_ms():
    return round((time.monotonic() - T0) * 1000, 1)


def record(ev, **fields):
    if not TIMELINE:
        return
    with timeline_lock, open(TIMELINE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now_ms(), "wall": round(time.time() * 1000), "ev": ev, **fields}) + "\n")


def reply(line):
    with out_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    record("out", line=line)


# --- guidepup socket ---------------------------------------------------------

clients = set()
clients_lock = threading.Lock()


def broadcast(message):
    data = (json.dumps(message) + "\n").encode()
    with clients_lock:
        for c in list(clients):
            try:
                c.sendall(data)
            except OSError:
                clients.discard(c)


def serve():
    os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen()
    while True:
        conn, _ = server.accept()
        with clients_lock:
            clients.add(conn)
        conn.sendall((json.dumps({"type": "ready"}) + "\n").encode())


threading.Thread(target=serve, daemon=True).start()

# --- espeak-ng via ctypes ----------------------------------------------------


class EspeakEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("unique_identifier", ctypes.c_uint),
        ("text_position", ctypes.c_int),
        ("length", ctypes.c_int),
        ("audio_position", ctypes.c_int),
        ("sample", ctypes.c_int),
        ("user_data", ctypes.c_void_p),
        ("id", ctypes.c_char * 8),
    ]


EVENT_LIST_TERMINATED, EVENT_WORD = 0, 1
SYNTH_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.POINTER(EspeakEvent))

espeak = ctypes.CDLL("libespeak-ng.so.1")
SAMPLE_RATE = espeak.espeak_Initialize(2, 0, None, 0)  # AUDIO_OUTPUT_SYNCHRONOUS
espeak.espeak_SetVoiceByName(b"en-us")
_pcm = bytearray()
_words = []


@SYNTH_CB
def _synth_callback(wav, numsamples, events):
    if numsamples > 0:
        _pcm.extend(ctypes.string_at(wav, numsamples * 2))
    i = 0
    while events[i].type != EVENT_LIST_TERMINATED:
        e = events[i]
        if e.type == EVENT_WORD:
            _words.append((e.audio_position, e.text_position, e.length))
        i += 1
    return 0


espeak.espeak_SetSynthCallback(_synth_callback)


def set_rate(speechd_rate):
    if speechd_rate < 0:
        wpm = ESPEAK_NORMAL_RATE + (ESPEAK_NORMAL_RATE - ESPEAK_MIN_RATE) * speechd_rate // 100
    else:
        wpm = ESPEAK_NORMAL_RATE + (ESPEAK_MAX_RATE - ESPEAK_NORMAL_RATE) * speechd_rate // 100
    espeak.espeak_SetParameter(1, wpm, 0)  # espeakRATE
    return wpm


def plain_text(ssml):
    return html.unescape(re.sub(r"<[^>]*>", "", ssml)).strip()


def synthesize(text):
    """Returns (pcm bytes, duration ms, [(start_ms, word)])."""
    _pcm.clear()
    _words.clear()
    raw = text.encode("utf-8") + b"\0"
    espeak.espeak_Synth(raw, len(raw), 0, 1, 0, 1, None, None)  # POS_CHARACTER, espeakCHARS_UTF8
    chars = list(text)
    words = []
    for audio_ms, pos, length in _words:
        words.append((audio_ms, "".join(chars[pos - 1 : pos - 1 + length])))
    duration = len(_pcm) / 2 / SAMPLE_RATE * 1000
    return bytes(_pcm), duration, words


# --- playback ----------------------------------------------------------------


class Utterance:
    counter = 0

    def __init__(self, kind, text):
        Utterance.counter += 1
        self.id = Utterance.counter
        self.kind = kind
        self.text = text
        self.cancel = threading.Event()
        self.started = None
        self.proc = None
        self.pcm, self.duration, self.words = (b"", 0.0, []) if MODE == "instant" else synthesize(text)

    def heard(self, elapsed_ms):
        full, partial = [], None
        for i, (start, word) in enumerate(self.words):
            end = self.words[i + 1][0] if i + 1 < len(self.words) else self.duration
            if end <= elapsed_ms:
                full.append(word)
            elif start <= elapsed_ms:
                partial = word
                break
        return " ".join(full), partial


current = None
current_lock = threading.Lock()


def feed(proc, pcm):
    try:
        for i in range(0, len(pcm), 4096):
            proc.stdin.write(pcm[i:i + 4096])
        proc.stdin.close()
    except (BrokenPipeError, ValueError, OSError):
        pass


def save_clip(utt, played_ms):
    if not CLIPS or not utt.pcm:
        return None
    os.makedirs(CLIPS, exist_ok=True)
    path = f"{CLIPS}/{os.getpid()}-{utt.id}.wav"
    n = min(len(utt.pcm) // 2, int(played_ms * SAMPLE_RATE / 1000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(utt.pcm[: n * 2])
    return path


def play(utt):
    """Plays (or just times) an utterance. Whoever takes it out of `current` first,
    this thread (END) or stop() (STOP), reports its outcome; the other stays quiet."""
    global current
    utt.started = time.monotonic()
    reply("701 BEGIN")
    record("begin", id=utt.id)
    if MODE == "audio" and utt.pcm:
        utt.proc = subprocess.Popen(
            ["pacat", "--playback", "--raw", "--format=s16le", "--channels=1", f"--rate={SAMPLE_RATE}",
             f"--latency-msec={PULSE_LATENCY_MS}", "--client-name=guidepup-lab"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if utt.cancel.is_set():
            utt.proc.kill()
        threading.Thread(target=feed, args=(utt.proc, utt.pcm), daemon=True).start()
    deadline = utt.started + utt.duration / 1000
    while not utt.cancel.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        utt.cancel.wait(min(remaining, 0.01))
    if utt.proc and not utt.cancel.is_set():
        utt.proc.wait()  # let PulseAudio drain the tail
    with current_lock:
        if current is not utt:
            return
        current = None
    record("end", id=utt.id, durMs=round(utt.duration, 1), clip=save_clip(utt, utt.duration))
    reply("702 END")


def speak(kind, text):
    global current
    utt = Utterance(kind, text)
    record("speak", id=utt.id, kind=kind, text=text, durMs=round(utt.duration, 1),
           words=[[round(s, 1), w] for s, w in utt.words])
    if MODE == "instant":
        reply("701 BEGIN")
        reply("702 END")
        return
    with current_lock:
        current = utt
    threading.Thread(target=play, args=(utt,), daemon=True).start()


def stop(kind):
    global current
    with current_lock:
        utt, current = current, None
    if utt is not None:
        utt.cancel.set()
        if utt.proc:
            utt.proc.kill()
        elapsed = (time.monotonic() - utt.started) * 1000 if utt.started else 0.0
        if MODE == "audio":
            elapsed = max(0.0, elapsed - PULSE_LATENCY_MS)
        heard, partial = utt.heard(elapsed)
        cut = {"id": utt.id, "text": utt.text, "heardMs": round(elapsed, 1), "durMs": round(utt.duration, 1),
               "heardText": heard, "partialWord": partial}
        record("cut", by=kind, clip=save_clip(utt, elapsed), **cut)
        broadcast({"type": "cut", "data": cut})
    else:
        # Nothing playing (the STOP crossed our END): like sd_espeak-ng, report nothing,
        # or speechd logs "unexpected event 703 STOP".
        record(kind, idle=True)
        broadcast({"type": kind.lower()})
        return
    broadcast({"type": kind.lower()})
    reply("704 PAUSE" if kind == "PAUSE" else "703 STOP")


# --- speechd module protocol -------------------------------------------------


def receive_data():
    lines = []
    for line in sys.stdin:
        line = line.rstrip("\n")
        if line == ".":
            return "\n".join(lines)
        lines.append("." if line == ".." else line)
    return None


def main():
    for line in sys.stdin:
        line = line.rstrip("\n")
        record("in", line=line)
        if line == "INIT":
            reply("299 OK LOADED")
        elif line == "AUDIO":
            reply("207 OK RECEIVING AUDIO SETTINGS")
            if receive_data() is None:
                break
            reply("203 OK AUDIO SETTINGS RECEIVED")
        elif line == "LOGLEVEL":
            reply("200 OK RECEIVING LOGLEVEL")
            if receive_data() is None:
                break
            reply("200 OK")
        elif line == "LIST VOICES":
            reply("200 OK")
        elif line == "SET":
            reply("203 OK RECEIVING SETTINGS")
            data = receive_data()
            if data is None:
                break
            record("set", data=data)
            for kv in data.split("\n"):
                key, _, value = kv.partition("=")
                if key == "rate" and value not in ("", "NULL"):
                    record("rate", speechd=int(value), wpm=set_rate(int(value)))
            reply("203 OK SETTINGS RECEIVED")
        elif line in ("SPEAK", "CHAR", "KEY", "SOUND_ICON"):
            reply("202 OK SEND DATA")
            data = receive_data()
            if data is None:
                break
            reply("200 OK SPEAKING")
            if line == "SPEAK":
                broadcast({"type": "speech", "data": data})
                speak("SPEAK", plain_text(data) or data)
            else:
                # The asset's module answers these without reading their data, so
                # guidepup never sees them. Spoken here, recorded but not broadcast.
                speak(line, data.replace("_", " "))
        elif line in ("STOP", "PAUSE", "CANCEL"):
            stop("STOP" if line == "CANCEL" else line)
        elif line in ("QUIT", "END"):
            reply("210 OK QUIT")
            break
        else:
            reply("200 OK")


try:
    main()
finally:
    try:
        os.unlink(SOCKET_PATH)
    except OSError:
        pass
