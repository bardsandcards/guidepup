# Speech + braille fidelity lab (not for merge)

Lab code behind https://github.com/bardsandcards/guidepup/issues/21 and https://github.com/guidepup/guidepup/issues/205:
what an Orca user actually hears and reads, compared with what guidepup records.

The branch is upstream `main` at `a7c5839` (0.40.0, Orca asset `0.3.0-51.1`) plus this directory and two test
folders. The library itself is unchanged.

- Findings, in the order they were measured: [`speech-fidelity/RESULTS.md`](speech-fidelity/RESULTS.md)
- Speech recognition benchmark: [`speech-fidelity/asr/REPORT.md`](speech-fidelity/asr/REPORT.md)

## Layout

| path | what |
|---|---|
| `build.sh`, `Dockerfile`, `speech-fidelity/image/Dockerfile` | the two images: an Ubuntu 26.04 Orca base, then espeak-ng, BRLTTY, liblouis, sox, ffmpeg |
| `sf.sh` | one lab run in a container (env options are in its header) |
| `modules/guidepup-timed.py` | a speech-dispatcher module that replaces the asset's. It synthesises with libespeak-ng (same rate mapping as `sd_espeak-ng`) and holds `END` for the real duration. `MODE=audio` plays it through PulseAudio. On `STOP` it logs which words were heard |
| `sf-brltty.sh`, `vr-display.py` | a 40-cell virtual braille display. BRLTTY's `vr` driver connects to it; it logs the text, dots and a liblouis back-translation of every refresh |
| `estimate.py` | estimates heard / cut / dropped from Orca 51's test-only speech log, with no timed module |
| `tl.py`, `view.py` | timelines merging speech, Orca's log, interrupts and braille |
| `audio_check.py`, `sd-durations*.{sh,py}` | check the timed module against recorded audio and the real `sd_espeak-ng` pipeline |
| `make_manifest.py` | turns the `CLIPS=1` runs into the real-session audio corpus |
| `batch*.sh` | the repeat batches behind RESULTS.md §6 |
| `../examples/playwright-orca/tests/lab/` | scenarios S1–S8 (`interrupts.spec.ts`) and the fixtures that turn on Orca's test logs (`fidelity.ts`) |
| `../examples/playwright-orca/tests/labup/` | upstream's `firefox.spec.ts` and `firefox-keyboard.spec.ts`, unchanged except for the fixture import (RESULTS.md §10) |
| `speech-fidelity/asr/` | the benchmark's scripts, per-clip results (`results.csv`) and tables. Models, venvs and audio are not included; `asr/README` says how to rebuild them |

## Running

```bash
.orca-lab/build.sh
MODE=timed BRLTTY=1 .orca-lab/sf.sh s3 tests/lab/interrupts.spec.ts -g S3
python3 .orca-lab/view.py .orca-lab/out/s3        # merged timeline per test
```

Output goes to `.orca-lab/out/<label>/`.

- `sf.sh` installs the Orca asset into `.orca-lab/sr` and swaps in the timed module (`MODE=asset` keeps the stock one).
- It also points the asset Orca's `tablesdir` at the system liblouis tables, so contracted braille works. The originals are kept as `*.asset`.
- The `guidepup-orca-cache` Docker volume holds Firefox and npm caches.
- Run one container at a time: AT-SPI and speech-dispatcher state in that volume is shared.

In the ASR scripts and report, "brief phrases" means the 15 seed phrases the benchmark started from (`scripts/phrases.py`).
