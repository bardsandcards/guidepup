// Times how long VoiceOver takes to answer its first AppleEvent after each
// way of launching it. Usage: node launch-paths.js <runs> <method>...
// Methods: open, cmdf5, starter (VoiceOverStarter, before macOS 27).
const { spawnSync } = require("child_process");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const running = () => spawnSync("pgrep", ["-x", "VoiceOver"]).status === 0;
const answers = () =>
  spawnSync("/usr/bin/osascript", [], {
    input: 'with timeout of 1 seconds\ntell application "VoiceOver"\nreturn enabled of caption window\nend tell\nend timeout',
    timeout: 2500,
  }).status === 0;
const APP = "/System/Library/CoreServices/VoiceOver.app";
const METHODS = {
  open: () => spawnSync("/usr/bin/open", ["-a", APP]),
  cmdf5: () => spawnSync("/usr/bin/osascript", ["-e", 'tell application "System Events" to key code 96 using command down']),
  starter: () => spawnSync(`${APP}/Contents/MacOS/VoiceOverStarter`),
};

(async () => {
  const runs = Number(process.argv[2]);
  for (const name of process.argv.slice(3)) {
    for (let i = 1; i <= runs; i++) {
      for (let j = 0; j < 60 && running(); j++) await sleep(500);
      if (running()) spawnSync("pkill", ["-x", "VoiceOver"]);
      await sleep(2000);
      const t0 = Date.now();
      const r = METHODS[name]();
      let proc = null, ans = null;
      while (Date.now() - t0 < 40000) {
        if (proc === null && running()) proc = (Date.now() - t0) / 1000;
        if (proc !== null && answers()) { ans = (Date.now() - t0) / 1000; break; }
        await sleep(200);
      }
      console.log(`${name} ${i}: launcher exit ${r.status}${r.error ? ` (${r.error.code})` : ""}, process at ${proc}s, first answer at ${ans}s`);
      await sleep(1500);
      spawnSync("/usr/bin/osascript", ["-e", 'tell application "VoiceOver" to quit'], { timeout: 8000 });
      for (let j = 0; j < 30 && running(); j++) await sleep(500);
      if (running()) spawnSync("pkill", ["-x", "VoiceOver"]);
    }
  }
})();
