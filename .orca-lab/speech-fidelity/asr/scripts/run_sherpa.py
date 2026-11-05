"""sherpa-onnx streaming zipformer transducer runner. Greedy search, num_threads=--threads.
Whole clip fed, then 0.66 s of trailing zeros and input_finished(), decoded until not ready
(otherwise the last word never flushes). Token timestamps -> word start; word end = next
token's timestamp or start + 0.04 s (approximate)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa

MODELS = {
    "zipformer-en-2023-06-26": ("csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26",
                                "{}-epoch-99-avg-1-chunk-16-left-128.int8.onnx"),
    "zipformer-en-kroko-2025-08-06": ("csukuangfj/sherpa-onnx-streaming-zipformer-en-kroko-2025-08-06",
                                      "{}.onnx"),
}


def load(model, threads):
    import numpy as np
    import sherpa_onnx
    from huggingface_hub import snapshot_download
    repo, pat = MODELS[model]
    d = Path(snapshot_download(repo, allow_patterns=[pat.format("*"), "tokens.txt", "*.md"]))
    rec = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(d / "tokens.txt"), encoder=str(d / pat.format("encoder")),
        decoder=str(d / pat.format("decoder")), joiner=str(d / pat.format("joiner")),
        num_threads=threads, sample_rate=16000, feature_dim=80, decoding_method="greedy_search",
        provider="cpu")

    def tr(x):
        s = rec.create_stream()
        s.accept_waveform(16000, x)
        s.accept_waveform(16000, np.zeros(int(0.66 * 16000), "float32"))
        s.input_finished()
        while rec.is_ready(s):
            rec.decode_stream(s)
        r = rec.get_result_all(s)
        toks, ts = list(r.tokens), list(r.timestamps)
        words = []
        for i, (t, st) in enumerate(zip(toks, ts)):
            end = ts[i + 1] if i + 1 < len(ts) else st + 0.04
            if t.startswith(("▁", " ")) or not words:
                words.append([t.lstrip("▁ "), round(st, 3), round(end, 3)])
            else:
                words[-1][0] += t
                words[-1][2] = round(end, 3)
        return r.text.strip(), [w for w in words if w[0]] or None
    return tr


if __name__ == "__main__":
    run(load, "sherpa-onnx")
