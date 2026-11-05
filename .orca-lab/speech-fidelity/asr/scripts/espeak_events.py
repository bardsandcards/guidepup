"""Runs INSIDE guidepup-orca:26.04-audio: synthesise each TTS text with libespeak-ng via ctypes
and record the synthesiser's own WORD events (sample position of each word start).
This is an independent word-timing ground truth for the espeak voices.
usage: python3 espeak_events.py /out/raw/_text/events_jobs.json /out/raw/_events.json"""
import ctypes as C, json, sys

lib = C.CDLL("libespeak-ng.so.1")


class EV(C.Structure):
    _fields_ = [("type", C.c_int), ("unique_identifier", C.c_uint), ("text_position", C.c_int),
                ("length", C.c_int), ("audio_position", C.c_int), ("sample", C.c_int),
                ("user_data", C.c_void_p), ("id", C.c_char * 8)]


CB = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_short), C.c_int, C.POINTER(EV))
state = {"n": 0, "words": []}


def cb(wav, n, ev):
    i = 0
    while ev[i].type != 0:
        if ev[i].type == 1:  # espeakEVENT_WORD
            state["words"].append({"text_position": ev[i].text_position, "length": ev[i].length,
                                   "audio_ms": ev[i].audio_position, "samples_at_cb": state["n"]})
        i += 1
    if wav:
        state["n"] += n
    return 0


cbf = CB(cb)
sr = lib.espeak_Initialize(1, 0, None, 0)  # AUDIO_OUTPUT_RETRIEVAL
lib.espeak_SetSynthCallback(cbf)
lib.espeak_SetVoiceByName(b"en-us")
jobs = json.load(open(sys.argv[1]))
out = {}
for j in jobs:
    lib.espeak_SetParameter(1, j["rate"], 0)  # espeakRATE
    state.update(n=0, words=[])
    t = j["text"].encode()
    lib.espeak_Synth(t, len(t) + 1, 0, 0, 0, 0x0, None, None)  # espeakCHARS_AUTO
    lib.espeak_Synchronize()
    out[j["key"]] = {"sr": sr, "total_samples": state["n"], "words": state["words"]}
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "done, sr", sr)
