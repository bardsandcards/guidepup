"""Synthesise every phrase (and, for the cross-check, every word-boundary prefix) with
espeak-ng 1.52 (docker image guidepup-orca:26.04-audio) at 175/300/450 wpm and Piper
en_US-lessac-medium at its default rate. Raw TTS output goes to corpus/raw/<voice>/.

Run with the align venv:  taskset -c 12-19 venvs/align/bin/python scripts/synth.py
"""
import json, os, re, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from textnorm import norm  # noqa: E402

ESPEAK_RATES = [175, 300, 450]
PIPER_MODEL = ROOT / "models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx"


def chunks(say):
    """Whitespace chunks of the TTS text with the spoken (aligner) words each contains."""
    out = []
    for c in say.split():
        out.append((c, re.findall(r"[a-z']+", c.lower())))
    return out


def prefix_texts(p):
    """Prefixes of the TTS text ending at a chunk boundary, keyed by spoken-word count."""
    cs = chunks(p["say"])
    res, nwords = {}, 0
    for i, (c, ws) in enumerate(cs[:-1]):
        nwords += len(ws)
        res[nwords] = " ".join(x for x, _ in cs[: i + 1])
    return res


def main():
    phrases = json.loads((ROOT / "phrases.json").read_text())
    jobs = []  # (voice, name, text)
    for p in phrases:
        for r in ESPEAK_RATES:
            jobs.append((f"espeak{r}", p["id"], p["say"]))
        jobs.append(("piper", p["id"], p["say"]))
        # prefix cross-check: brief + extra phrases only, espeak 175 & 450 + piper
        if p["source"] in ("brief", "extra"):
            for nw, t in prefix_texts(p).items():
                for v in ("espeak175", "espeak450", "piper"):
                    jobs.append((v, f"{p['id']}_pre{nw}", t))

    raw = ROOT / "corpus/raw"
    txt = ROOT / "corpus/raw/_text"
    txt.mkdir(parents=True, exist_ok=True)
    lines = ["set -e"]
    piper_jobs = []
    for voice, name, text in jobs:
        (raw / voice).mkdir(parents=True, exist_ok=True)
        if voice == "piper":
            piper_jobs.append((name, text))
            continue
        tf = txt / f"{voice}_{name}.txt"
        tf.write_text(text)
        rate = voice.removeprefix("espeak")
        lines.append(f"espeak-ng -v en-us -s {rate} -f /out/raw/_text/{tf.name} -w /out/raw/{voice}/{name}.wav")
    (txt / "espeak_jobs.sh").write_text("\n".join(lines) + "\n")
    print(f"espeak jobs: {len(lines)-1}, piper jobs: {len(piper_jobs)}", flush=True)
    subprocess.run([
        "docker", "run", "--rm", "--cpuset-cpus=12-19", "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{ROOT/'corpus'}:/out", "--entrypoint", "sh", "guidepup-orca:26.04-audio",
        "/out/raw/_text/espeak_jobs.sh"], check=True)

    from piper import PiperVoice, SynthesisConfig
    voice = PiperVoice.load(str(PIPER_MODEL))
    cfg = SynthesisConfig()  # default length/noise scales ("normal rate")
    for name, text in piper_jobs:
        with wave.open(str(raw / "piper" / f"{name}.wav"), "wb") as w:
            voice.synthesize_wav(text, w, syn_config=cfg)
    print("done", flush=True)


if __name__ == "__main__":
    main()
