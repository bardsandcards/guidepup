"""Stage 2: resample raw TTS to 16 kHz, trim, pad 300 ms, force-align spoken words.
Writes corpus/full/<voice>/<pid>.wav and corpus/align.json; also measures prefix-TTS
durations for the cross-check (corpus/prefix_check.json)."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audio import load16k, trim, pad, write, SR, PAD  # noqa
from align import align_words  # noqa

VOICES = ["espeak175", "espeak300", "espeak450", "piper"]


def spoken_words(say):
    return re.findall(r"[a-z']+", say.lower())


def main():
    phrases = json.loads((ROOT / "phrases.json").read_text())
    res, pre = {}, []
    for v in VOICES:
        (ROOT / "corpus/full" / v).mkdir(parents=True, exist_ok=True)
        for p in phrases:
            x = pad(trim(load16k(ROOT / f"corpus/raw/{v}/{p['id']}.wav")))
            write(ROOT / f"corpus/full/{v}/{p['id']}.wav", x)
            words = spoken_words(p["say"])
            al = align_words(x, words)
            res[f"{v}/{p['id']}"] = {"dur": len(x) / SR, "words": al}
            for f in sorted((ROOT / f"corpus/raw/{v}").glob(f"{p['id']}_pre*.wav")):
                nw = int(f.stem.split("_pre")[1])
                y = trim(load16k(f))
                pre.append({"voice": v, "pid": p["id"], "nwords": nw,
                            "prefix_tts_end": PAD + len(y) / SR,
                            "align_end": al[nw - 1][2],
                            "next_start": al[nw][1] if nw < len(al) else None})
        print(v, "aligned", flush=True)
    (ROOT / "corpus/align.json").write_text(json.dumps(res, indent=0))
    (ROOT / "corpus/prefix_check.json").write_text(json.dumps(pre, indent=0))


if __name__ == "__main__":
    main()
