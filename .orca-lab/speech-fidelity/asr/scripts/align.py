"""Forced alignment of spoken words with torchaudio's MMS_FA (wav2vec2 CTC, 20 ms frames)."""
import torch, torchaudio
from torchaudio.pipelines import MMS_FA

torch.set_num_threads(4)
_model = _tok = _aligner = None


def _load():
    global _model, _tok, _aligner
    if _model is None:
        _model = MMS_FA.get_model(with_star=False).eval()
        _tok = MMS_FA.get_tokenizer()
        _aligner = MMS_FA.get_aligner()


def align_words(x, words, sr=16000):
    """Return [(word, start_s, end_s, score)] for each word (a-z' only)."""
    _load()
    wav = torch.from_numpy(x).unsqueeze(0)
    with torch.inference_mode():
        emission, _ = _model(wav)
    spans = _aligner(emission[0], _tok(words))
    ratio = wav.size(1) / emission.size(1) / sr
    out = []
    for w, s in zip(words, spans):
        score = sum(t.score * (t.end - t.start) for t in s) / sum(t.end - t.start for t in s)
        out.append((w, s[0].start * ratio, s[-1].end * ratio, float(score)))
    return out
