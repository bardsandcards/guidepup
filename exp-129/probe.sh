#!/bin/zsh
# Usage: probe.sh <path-to-MacOSATDriverServer.app> <label>
# Registers the speech extension, has `say` speak through it, and reports
# what reached the socket and what the extension logged. Leaves it unregistered.
APP=$1; LABEL=$2
EXT=com.bocoup.MacOSATDriverServer.MacOSATDriverServerExtension
LSREG=/System/Library/Frameworks/CoreServices.framework/Versions/Current/Frameworks/LaunchServices.framework/Versions/Current/Support/lsregister
SOCK=/tmp/at_driver_generic/driver.socket
echo "### $LABEL ($(sw_vers -productVersion) $(sw_vers -buildVersion))"
codesign -dvv "$APP/Contents/PlugIns/MacOSATDriverServerExtension.appex" 2>&1 | grep -E "^Signature|^TeamIdentifier"
xattr -r -d com.apple.quarantine "$APP" 2>/dev/null
$LSREG -f -R -trusted "$APP"
pluginkit -e use -i $EXT
for i in {1..30}; do say -v '?' | grep -q MacOSATDriverServerExtensionVoice && break; sleep 1; done
echo "voice listed after ${i}s"
pluginkit -m -i $EXT | sed 's/\t.*//'
auval -v ausp atdg BOCU 2>&1 | grep -E "VALIDATION|FATAL"
say -v '?' | grep -c MacOSATDriverServerExtensionVoice | sed 's/^/voices listed: /'
mkdir -p /tmp/at_driver_generic && rm -f $SOCK
nc -lkU $SOCK > /tmp/socket.out 2>&1 & NC=$!
/usr/bin/log stream --style compact --level debug --predicate 'subsystem == "com.bocoup.MacOSATDriverServer" OR (process == "say" AND (eventMessage CONTAINS "wildcard" OR eventMessage CONTAINS "Utterance encountered" OR eventMessage CONTAINS "MauiEngine] Starting speech"))' > /tmp/probe.log 2>&1 & LG=$!
sleep 2
say -v MacOSATDriverServerExtensionVoice "probe from the VM"
sleep 4
kill $NC $LG 2>/dev/null
echo "socket received: $(wc -c < /tmp/socket.out | tr -d ' ') bytes: $(head -c 200 /tmp/socket.out)"
grep -v "^Filtering\|^Timestamp" /tmp/probe.log | sed -E 's/^[^ ]+ ([^ ]+) [A-Za-z]+ /\1 /' | cut -c1-170
pluginkit -e ignore -i $EXT; $LSREG -u "$APP"; pkill -f MacOSATDriverServerExtension
echo
