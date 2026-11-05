#!/usr/bin/env bash
cd "$(dirname "$0")/.."
NOECHO='[typing-echo]\nkey-echo=false'
MODE=timed CLIPS=1 INI_EXTRA="$NOECHO" REPEAT=3 .orca-lab/sf.sh corpus-r50 tests/lab/interrupts.spec.ts -g "S[1-6]"
MODE=timed CLIPS=1 RATE=100 INI_EXTRA="$NOECHO" REPEAT=3 .orca-lab/sf.sh corpus-r100 tests/lab/interrupts.spec.ts -g "S[1-6]"
MODE=timed CLIPS=1 REPEAT=2 .orca-lab/sf.sh corpus-echo-r50 tests/lab/interrupts.spec.ts -g "S[47]"
echo BATCH2 DONE
