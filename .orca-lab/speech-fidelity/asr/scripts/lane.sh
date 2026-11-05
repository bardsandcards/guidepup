#!/bin/sh
# Run a list of runner commands sequentially on one 4-core lane.
# usage: scripts/lane.sh <cpus> <jobfile>   (jobfile: one "venv runner model subset outname" per line)
cd "$(dirname "$0")/.."
cpus=$1; jobs=$2
while read -r venv runner model subset name; do
  case "$venv" in ''|\#*) continue;; esac
  out=out/$subset/$name.jsonl
  if [ -s "$out" ] && tail -1 "$out" | grep -q '"meta"'; then echo "skip $name/$subset"; continue; fi
  echo "$(date -Is) start $name $subset on $cpus"
  PIN_CPUS=$cpus tools/pin.sh venvs/$venv/bin/python scripts/$runner --model "$model" --subset "$subset" --out "$out" $( [ "$subset" = det ] && echo --repeat 3 ) > logs/run-$subset-$name.log 2>&1 \
    && echo "$(date -Is) done $name" || echo "$(date -Is) FAILED $name (see logs/run-$subset-$name.log)"
done < "$jobs"
