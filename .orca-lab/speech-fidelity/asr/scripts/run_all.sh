#!/bin/sh
# Reproduce the whole benchmark from scratch (about 4-5 h on 8 E-cores).
# Note: the job lists (scripts/jobs_*.txt) are the final ones; during the overnight run some
# jobs were moved between lanes/subsets by hand (see REPORT.md caveats).
# Everything is pinned to CPUs 12-19 via tools/pin.sh (taskset + affinity shim).
set -e
cd "$(dirname "$0")/.."
[ -f tools/pincpu.so ] || gcc -O2 -shared -fPIC -o tools/pincpu.so tools/pincpu.c -ldl
scripts/setup_venvs.sh                      # one uv venv per model family (+ venvs/align, see README)
python3 scripts/phrases.py > phrases.json
tools/pin.sh venvs/align/bin/python scripts/synth.py         # espeak (docker) + Piper
tools/pin.sh venvs/align/bin/python scripts/align_corpus.py  # 16 kHz, trim, pad, MMS_FA
tools/pin.sh venvs/align/bin/python scripts/build_clips.py   # clips + manifest
docker run --rm --cpuset-cpus=12-19 --user "$(id -u):$(id -g)" -v "$PWD/corpus:/out" \
  -v "$PWD/scripts:/s:ro" --entrypoint python3 guidepup-orca:26.04-audio \
  /s/espeak_events.py /out/raw/_text/events_jobs.json /out/raw/_events.json
venvs/align/bin/python scripts/check_events.py
venvs/align/bin/python scripts/make_subsets.py
venvs/align/bin/python scripts/make_sil.py      # 20 extra silence/noise clips (own manifest)
tools/pin.sh venvs/align/bin/python scripts/build_real.py ../../out/real-corpus-manifest.jsonl   # real Orca corpus (make_manifest.py)
# correctness runs: two 4-core lanes
scripts/lane.sh 12-15 scripts/jobs_laneA.txt & scripts/lane.sh 16-19 scripts/jobs_laneB.txt & wait
# silence set and determinism (3 repeats), then timing alone on 12-15
scripts/lane.sh 12-15 scripts/jobs_sil.txt
scripts/lane.sh 12-15 scripts/jobs_det.txt
scripts/lane.sh 12-15 scripts/jobs_timing.txt
scripts/score_all.sh
venvs/align/bin/python scripts/summarize_real.py
venvs/align/bin/python scripts/decision.py
python3 scripts/update_report.py
