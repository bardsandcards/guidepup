#!/bin/sh
# After lane A's correctness jobs: silence set, then determinism, on 12-15.
cd "$(dirname "$0")/.."
while kill -0 "$1" 2>/dev/null; do sleep 10; done
scripts/lane.sh 12-15 scripts/jobs_sil.txt
scripts/lane.sh 12-15 scripts/jobs_det.txt
