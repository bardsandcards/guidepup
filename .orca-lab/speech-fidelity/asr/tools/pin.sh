#!/bin/sh
# Run a command on CPUs 12-19 (or $PIN_CPUS) with the affinity shim preloaded.
here=$(dirname "$(readlink -f "$0")")
exec taskset -c "${PIN_CPUS:-12-19}" env LD_PRELOAD="$here/pincpu.so${LD_PRELOAD:+:$LD_PRELOAD}" "$@"
