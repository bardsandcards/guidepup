#!/bin/sh
# usage: scripts/after.sh <pid> <cpus> <jobfile>: wait for pid to exit, then run the lane
while kill -0 "$1" 2>/dev/null; do sleep 5; done
exec "$(dirname "$0")/lane.sh" "$2" "$3"
