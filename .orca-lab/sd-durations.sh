#!/usr/bin/env bash
# Times real sd_espeak-ng output (speech-dispatcher → module → PulseAudio null sink)
# for a few phrases at rate 0 and 100, to check the lab module's durations.
# Runs in guidepup-orca:26.04-audio WITHOUT the shared cache volume.
set -eu
export XDG_RUNTIME_DIR=/tmp/xdg; mkdir -p -m 0700 $XDG_RUNTIME_DIR
OUT=/work/.orca-lab/out/sd-durations; rm -rf $OUT; mkdir -p $OUT
pulseaudio -D -n --exit-idle-time=-1 --load=module-native-protocol-unix \
  --load="module-null-sink sink_name=lab rate=22050 channels=1" --load=module-always-sink
for i in $(seq 50); do pactl info >/dev/null 2>&1 && break; sleep 0.1; done
pactl set-default-sink lab
mkdir -p /tmp/sd
cat > /tmp/sd/speechd.conf <<EOF
AudioOutputMethod "pulse"
AddModule "espeak-ng" "sd_espeak-ng" "espeak-ng.conf"
DefaultModule espeak-ng
DefaultLanguage "en-US"
DefaultPunctuationMode "most"
EOF
speech-dispatcher -s -C /tmp/sd -c unix_socket -S /tmp/sd/sock -t 0 -l 1 -L /tmp/sd &
for i in $(seq 50); do [ -S /tmp/sd/sock ] && break; sleep 0.1; done
export SPEECHD_ADDRESS=unix_socket:/tmp/sd/sock
spd-say -w -r 0 "warm up" || true
while IFS= read -r text; do
  for rate in 0 100; do
    f=$OUT/$(echo -n "$text$rate" | md5sum | cut -c1-8).wav
    parecord -d lab.monitor --file-format=wav --rate=22050 --channels=1 "$f" & rec=$!
    sleep 0.4
    spd-say -w -r $rate -m most "$text"
    sleep 0.4
    kill -INT $rec; wait $rec 2>/dev/null || true
    printf '%s\t%s\t%s\n' "$rate" "$f" "$text" >> $OUT/index.tsv
  done
done <<'EOF'
Apply the twenty percent seasonal discount to every item in your basket before checkout button
Saved. Your changes were stored.
Your order has been placed and a confirmation email is on its way to your inbox now
Start button
Review the shipping address and delivery window for this order before you pay button
EOF
python3 /work/.orca-lab/sd-durations-compare.py $OUT/index.tsv
