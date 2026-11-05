"""Where was it cut? Score every word prefix of the KNOWN text against the audio with CTC.

No transcription: for a clip whose expected words are w1..wn, compute
    loss(j) = -log P(chars of w1..wj | audio)        j = 0..n
with MMS_FA's emissions (wav2vec2 CTC over characters) and take k_hat = argmin_j loss(j).
Every hypothesis explains the same frames, so a too-short prefix pays for speech frames it
leaves as blank and a too-long prefix pays for characters squeezed into silence.

    prefix_ctc.py <out.jsonl> <manifest.jsonl> [subset.txt]

Writes one row per clip: clip, n, k, type, k_hat, losses, ms (compute time).
"""
import json
import sys
import time

import torch
import torch.nn.functional as F
from torchaudio.pipelines import MMS_FA

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audio import load16k  # noqa: E402
from spoken import spoken  # noqa: E402

torch.set_num_threads(4)

out_path, manifest = sys.argv[1], sys.argv[2]
keep = set(open(sys.argv[3]).read().split()) if len(sys.argv) > 3 else None
model = MMS_FA.get_model(with_star=False).eval()
tok = MMS_FA.get_tokenizer()
clip_dir = __file__.rsplit("/", 2)[0] + "/corpus/clips"

with open(out_path, "w") as out:
    for line in open(manifest):
        r = json.loads(line)
        if keep is not None and r["clip"] not in keep or r["type"] not in ("full", "trunc", "mid"):
            continue
        t0 = time.perf_counter()
        x = load16k(f"{clip_dir}/{r['clip']}.wav")
        with torch.inference_mode():
            em, _ = model(torch.from_numpy(x).unsqueeze(0))
            lp = F.log_softmax(em, dim=-1).transpose(0, 1)  # (T, 1, C)
            words = [tok([spoken(w)])[0] for w in r["ref"]]
            losses = []
            for j in range(len(words) + 1):
                tgt = [c for w in words[:j] for c in w]
                losses.append(float(F.ctc_loss(lp, torch.tensor([tgt], dtype=torch.long),
                                               torch.tensor([lp.size(0)]), torch.tensor([len(tgt)]),
                                               blank=0, reduction="sum", zero_infinity=False)))
        k_hat = min(range(len(losses)), key=losses.__getitem__)
        out.write(json.dumps({"clip": r["clip"], "n": r["n"], "k": r["k"], "type": r["type"],
                              "voice": r["voice"], "kind": r.get("kind"), "heardMs": r.get("heardMs"),
                              "k_hat": k_hat, "losses": [round(v, 2) for v in losses],
                              "ms": round((time.perf_counter() - t0) * 1000)}) + "\n")
