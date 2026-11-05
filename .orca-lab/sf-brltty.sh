#!/usr/bin/env bash
# Starts a 40-cell virtual braille display (vr-display.py) and brltty driving it,
# with BrlAPI open to the session user, before Orca starts. Logs to $LAB_OUT/vr.jsonl.
set -e
mkdir -p /tmp/brl
python3 /work/.orca-lab/vr-display.py /tmp/brl/vr.sock "${BRL_CELLS:-40}" "$LAB_OUT/vr.jsonl" &
for i in $(seq 50); do [ -S /tmp/brl/vr.sock ] && break; sleep 0.1; done
sudo mkdir -p /var/lib/BrlAPI
sudo brltty -q -b vr -d client:/tmp/brl/vr.sock -x no -A auth=none -l info -L "$LAB_OUT/brltty.log"
for i in $(seq 100); do [ -S /var/lib/BrlAPI/0 ] && grep -q '"connected"' "$LAB_OUT/vr.jsonl" 2>/dev/null && break; sleep 0.1; done
echo "brltty ready"
