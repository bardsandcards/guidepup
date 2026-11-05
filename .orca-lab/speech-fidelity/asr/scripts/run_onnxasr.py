"""onnx-asr runner (NeMo Parakeet TDT, NeMo Canary AED). int8 weights, ORT CPU,
intra_op threads = --threads, inter_op 1. Greedy decoding (the package's only mode).
Word times are built from token timestamps (token start times): a word starts at its first
token and ends at its last token's start + one encoder frame (80 ms for these FastConformers)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_common import run, ROOT  # noqa

FRAME = 0.08
MODELS = {
    "parakeet-tdt-0.6b-v2": ("nemo-parakeet-tdt-0.6b-v2", None, {}),
    "parakeet-tdt-0.6b-v3": ("nemo-parakeet-tdt-0.6b-v3", None, {}),
    "canary-180m-flash": ("nemo-conformer-aed", "istupakov/canary-180m-flash-onnx", {"language": "en", "pnc": True}),
}


def load(model, threads):
    import onnxruntime as rt
    import onnx_asr
    from huggingface_hub import snapshot_download
    name, repo, opts = MODELS[model]
    so = rt.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    path = snapshot_download(repo, allow_patterns=["*.int8.onnx", "*.txt", "*.json", "nemo*.onnx"]) if repo else None
    m = onnx_asr.load_model(name, path, quantization="int8", sess_options=so,
                            providers=["CPUExecutionProvider"]).with_timestamps()

    def tr(x):
        r = m.recognize(x, sample_rate=16000, **opts)
        words = []
        if r.tokens and r.timestamps:
            for tok, ts in zip(r.tokens, r.timestamps):
                if tok.startswith((" ", "▁")) or not words:
                    words.append([tok.strip().lstrip("▁"), round(ts, 3), round(ts + FRAME, 3)])
                else:
                    words[-1][0] += tok
                    words[-1][2] = round(ts + FRAME, 3)
            words = [w for w in words if w[0]]
        return r.text.strip(), words or None
    return tr


if __name__ == "__main__":
    run(load, "onnx-asr")
