#!/bin/sh
# Score every complete output (all/core/mini/sil) and rebuild summary tables.
cd "$(dirname "$0")/.."
f=""
for p in out/all/*.jsonl out/core/*.jsonl out/mini/*.jsonl out/turbo/*.jsonl out/sil/*.jsonl out/real/*.jsonl; do
  [ -f "$p" ] && tail -1 "$p" | grep -q '"meta"' && f="$f $p"
done
taskset -c 16-19 venvs/align/bin/python scripts/score.py $f && taskset -c 16-19 venvs/align/bin/python scripts/summarize.py > /dev/null
