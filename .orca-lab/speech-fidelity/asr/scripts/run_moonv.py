"""Moonshine v2 streaming models via moonshine-voice (native libmoonshine, ORT quantized
models from download.moonshine.ai, not HF). transcribe_without_streaming on the whole clip,
word timestamps only for model names ending "+wts" (slow). The library segments with its built-in Silero VAD; that is part
of the library's normal path and is left on (noted in the report)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa

ARCH = {"tiny-streaming": 2, "small-streaming": 4, "medium-streaming": 5, "tiny": 0, "base": 1}


def load(model, threads):
    wts = model.endswith("+wts")
    model = model.removesuffix("+wts")
    from moonshine_voice import download as d
    from moonshine_voice.moonshine_api import ModelArch
    from moonshine_voice.transcriber import Transcriber
    arch = ModelArch(ARCH[model])
    info = d.find_model_info("en", arch)
    path, _ = d.download_model_from_info(info, cache_root=ROOT / "models/moonshine-voice",
                                          include_word_timestamps=wts)
    t = Transcriber(str(path), arch, options={"word_timestamps": "true"} if wts else None)

    def tr(x):
        tx = t.transcribe_without_streaming(x.tolist(), 16000)
        texts, words = [], []
        for line in tx.lines:
            texts.append(line.text.strip())
            for w in (line.words or []):
                words.append([w.word.strip(), round(w.start, 3), round(w.end, 3)])
        return " ".join(x for x in texts if x), words or None
    return tr


if __name__ == "__main__":
    run(load, "moonshine-voice")
