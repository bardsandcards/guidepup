"""Vosk (Kaldi) runner. One recognizer, Reset() per clip; whole clip fed at once, FinalResult,
word times on (SetWords). Kaldi decoding here is single-threaded."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa


def load(model, threads):
    import numpy as np
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    m = Model(str(ROOT / "models/vosk" / model))
    rec = KaldiRecognizer(m, 16000)  # reused: building one per clip costs ~5 s with lgraph
    rec.SetWords(True)

    fed = [0.0]  # Reset() keeps the time base running, so subtract the audio already fed

    def tr(x):
        rec.Reset()
        off = fed[0]
        fed[0] += len(x) / 16000
        pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
        rec.AcceptWaveform(pcm)
        r = json.loads(rec.FinalResult())
        words = [[w["word"], round(w["start"] - off, 3), round(w["end"] - off, 3)] for w in r.get("result", [])]
        return r.get("text", ""), words
    return tr


if __name__ == "__main__":
    run(load, "vosk")
