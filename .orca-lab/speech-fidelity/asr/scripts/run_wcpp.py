"""whisper.cpp runner via pywhispercpp (ggml models from ggerganov/whisper.cpp on HF).
Decoding: greedy (best_of 1), temperature 0, temperature_inc 0 (no fallback), no_context,
language en, token timestamps on, split_on_word + max_len 1 so each segment is one word."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa


def load(model, threads):
    from huggingface_hub import hf_hub_download
    from pywhispercpp.model import Model
    path = hf_hub_download("ggerganov/whisper.cpp", f"ggml-{model}.bin")
    m = Model(path, n_threads=threads, print_progress=False, print_realtime=False,
              language="en", temperature=0.0, temperature_inc=0.0, no_context=True,
              token_timestamps=True, max_len=1, split_on_word=True, redirect_whispercpp_logs_to=None)

    def tr(x):
        segs = m.transcribe(x, n_processors=None)
        words = [[s.text.strip(), s.t0 / 100, s.t1 / 100] for s in segs if s.text.strip()]
        text = " ".join(w[0] for w in words)
        return text, words
    return tr


if __name__ == "__main__":
    run(load, "whisper.cpp")
