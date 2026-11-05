#!/usr/bin/env bash
cd "$(dirname "$0")/.."
MODE=asset .orca-lab/sf.sh up-asset tests/labup/
MODE=timed .orca-lab/sf.sh up-timed tests/labup/
MODE=timed RATE=100 .orca-lab/sf.sh up-timed-r100 tests/labup/
echo BATCH3 DONE
