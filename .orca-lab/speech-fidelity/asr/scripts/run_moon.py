"""Moonshine (original tiny/base, ONNX float) via useful-moonshine-onnx. Greedy decoding
(the package's only mode); max_len = 6 tokens per second of audio as in Moonshine's own
examples, minimum 8. ORT sessions get intra_op threads = --threads (the package passes no
SessionOptions, so InferenceSession is wrapped). No word timestamps."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa


def load(model, threads):
    import onnxruntime as rt
    so = rt.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    _IS = rt.InferenceSession
    rt.InferenceSession = lambda path, *a, **k: _IS(path, sess_options=so, providers=["CPUExecutionProvider"])
    import moonshine_onnx
    from moonshine_onnx.transcribe import load_tokenizer
    m = moonshine_onnx.MoonshineOnnxModel(model_name=model)
    tok = load_tokenizer()

    def tr(x):
        n = max(8, int(len(x) / 16000 * 6))
        toks = m.generate(x[None, :].astype("float32"), max_len=n)
        return tok.decode_batch(toks)[0].strip(), None
    return tr


if __name__ == "__main__":
    run(load, "moonshine-onnx")
