#!/usr/bin/env bash
# Speech-fidelity lab run (bardsandcards/guidepup#21). One container at a time.
#   .orca-lab/sf.sh <label> [playwright test filter...]
# Env:
#   MODE=asset|instant|timed|audio  speech module (asset = the asset's own module)
#   RATE=<0-100>                    Orca voice rate, written to voice-sets/primary/default (Orca 51
#                                   ignores the profile's [voice] rate=100, so unset = Orca's 50)
#   INI_EXTRA='<ini text>'          appended to guidepup.ini (e.g. key echo off)
#   BRLTTY=1                        start brltty (see sf-brltty.sh) before Orca
#   REPEAT=<n>                      playwright --repeat-each
# Output: .orca-lab/out/<label>/ (playwright log, timeline.jsonl, orca-*.jsonl, session.wav)
set -u
WT=$(cd "$(dirname "$0")/.." && pwd)
LABEL=$1; shift
FILTER=${*:-tests/lab/}
OUT=$WT/.orca-lab/out/$LABEL
rm -rf "$OUT"; mkdir -p "$OUT"
docker run --rm --init --shm-size=1g --cpuset-cpus=0-7 \
  -e CI=true -e ORCA_TEST_RPC_SECRET=lab -e GUIDEPUP_SCREEN_READERS_PATH=/work/.orca-lab/sr \
  -e MODE="${MODE:-timed}" -e RATE="${RATE:-}" -e INI_EXTRA="${INI_EXTRA:-}" -e BRLTTY="${BRLTTY:-0}" -e REPEAT="${REPEAT:-}" \
  -e LAB_OUT="/work/.orca-lab/out/$LABEL" -e GP_TIMELINE="/work/.orca-lab/out/$LABEL/timeline.jsonl" \
  -e GP_SPEECH_MODE="${MODE:-timed}" -e GP_CLIPS_DIR="${CLIPS:+/work/.orca-lab/out/$LABEL/played}" -e XDG_RUNTIME_DIR=/tmp/xdg \
  -v "$WT:/work" -v guidepup-orca-cache:/home/ubuntu/.cache guidepup-orca:26.04-audio bash -lc '
set -e
mkdir -p -m 0700 /tmp/xdg
[ -d node_modules ] || npm ci --no-audit --no-fund --no-progress >/dev/null 2>&1
[ -d examples/playwright-orca/node_modules ] || {
  npm ci --prefix ./examples/playwright-orca --no-audit --no-fund --no-progress >/dev/null 2>&1
  npm --prefix ./examples/playwright-orca rebuild ffmpeg-static --ignore-scripts=false >/dev/null 2>&1; }
npm --prefix ./examples/playwright-orca run browsers >/dev/null 2>&1
A=/work/.orca-lab/sr/orca/7/0.3.0-51.1/extracted
[ -d $A ] || npx -y --min-release-age=0 --ignore-scripts=false @guidepup/setup@0.29.2 install >/dev/null 2>&1
[ -f $A/speechd/modules/guidepup.asset ] || cp $A/speechd/modules/guidepup $A/speechd/modules/guidepup.asset
[ -f $A/guidepup.ini.asset ] || cp $A/guidepup.ini $A/guidepup.ini.asset
# The asset Orca has an empty tablesdir, so no liblouis and no contracted braille: use the system tables.
P=$A/lib/python3/dist-packages/orca/orca_platform.py
[ -f $P.asset ] || { cp $P $P.asset; sed -i "s|^tablesdir = \"\"\$|tablesdir = \"/usr/share/liblouis/tables\"|" $P; }
if [ "$MODE" = asset ]; then cp $A/speechd/modules/guidepup.asset $A/speechd/modules/guidepup
else cp /work/.orca-lab/modules/guidepup-timed.py $A/speechd/modules/guidepup; fi
chmod +x $A/speechd/modules/guidepup
{ cat $A/guidepup.ini.asset; [ -n "$RATE" ] && printf "\n[voice-sets/primary/default]\nrate=%s\n" "$RATE"; printf "%b\n" "$INI_EXTRA"; } > $A/guidepup.ini
cp $A/guidepup.ini "$LAB_OUT/guidepup.ini"
REC=
if [ "$MODE" = audio ]; then
  pulseaudio -D -n --exit-idle-time=-1 --load=module-native-protocol-unix \
    --load="module-null-sink sink_name=lab rate=22050 channels=1" --load="module-always-sink" 2>"$LAB_OUT/pulse.err"
  for i in $(seq 50); do pactl info >/dev/null 2>&1 && break; sleep 0.1; done
  pactl set-default-sink lab
  parecord -d lab.monitor --file-format=wav --rate=16000 --channels=1 "$LAB_OUT/session.wav" & REC=$!
  date +%s%3N > "$LAB_OUT/session.wav.start"
fi
cd examples/playwright-orca
set +e
xvfb-run -a dbus-run-session -- bash -c "[ \"$BRLTTY\" = 1 ] && /work/.orca-lab/sf-brltty.sh; npx playwright test -c firefox.config.ts --retries 0 --workers 1 --reporter=list ${REPEAT:+--repeat-each $REPEAT} '"$FILTER"'"
status=$?
[ -n "$REC" ] && { sleep 0.5; kill -INT $REC; wait $REC 2>/dev/null; }
exit $status
' > "$OUT/playwright.log" 2>&1
status=$?
echo "[$LABEL] exit=$status $(grep -E '^\s+[0-9]+ (passed|failed|flaky)' "$OUT/playwright.log" | tr -s ' ' | tr '\n' ' ')"
exit $status
