#!/usr/bin/env bash
cd "$(dirname "$0")/.."
NOECHO='[typing-echo]\nkey-echo=false'
MODE=timed BRLTTY=1 INI_EXTRA="$NOECHO" REPEAT=5 .orca-lab/sf.sh rep-r50 tests/lab/interrupts.spec.ts -g "S[1-6]"
MODE=timed BRLTTY=1 RATE=100 INI_EXTRA="$NOECHO" REPEAT=5 .orca-lab/sf.sh rep-r100 tests/lab/interrupts.spec.ts -g "S[1-6]"
MODE=asset BRLTTY=1 INI_EXTRA="$NOECHO" REPEAT=5 .orca-lab/sf.sh rep-asset tests/lab/interrupts.spec.ts -g "S[1-6]"
echo BATCH1 DONE
