"""faster-whisper (CTranslate2) runner. Model names are HF repo ids; compute_type int8.
Decoding: beam 5, temperature 0.0 only (no fallback), condition_on_previous_text=False,
no VAD filter, language en, word timestamps on."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa


def load(model, threads):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=threads, num_workers=1,
                     download_root=str(ROOT / "models/fw"))

    def tr(x):
        segs, _ = m.transcribe(x, language="en", beam_size=5, temperature=0.0,
                               condition_on_previous_text=False, vad_filter=False,
                               word_timestamps=True)
        segs = list(segs)
        text = " ".join(s.text.strip() for s in segs).strip()
        words = [[w.word.strip(), round(w.start, 3), round(w.end, 3)] for s in segs for w in (s.words or [])]
        return text, words
    return tr


if __name__ == "__main__":
    run(load, "faster-whisper")
