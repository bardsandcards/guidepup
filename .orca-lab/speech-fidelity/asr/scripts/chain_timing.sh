#!/bin/sh
# Timing pass alone: wait until no other benchmark lane/chain is running, then time on 12-15.
cd "$(dirname "$0")/.."
while pgrep -f 'jobs_laneA.txt|jobs_laneB.txt|chain_after_A.sh|jobs_sil.txt|jobs_det.txt' > /dev/null; do sleep 15; done
echo "$(date -Is) timing pass starts (nothing else of ours running on 12-19)"
scripts/lane.sh 12-15 scripts/jobs_timing.txt
echo "$(date -Is) timing pass done"
